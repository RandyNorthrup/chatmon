# M8: Translation plumbing

Milestone M8 of the [improvement roadmap](ROADMAP.md), assessment item M8-01. Branch `wave3/m8`, from
`improve/assessment-fixes` at `cac0047`. The ledger at the end owns every requirement, task, state and receipt.
Reports, logs and the drill spec are in [reports/m8/](reports/m8/).

## Rationale

### Scope

Every string Chatmon shows can be translated, with only English shipped, and adding a language is one `.po` file.
M8 runs in two phases, because M7 is changing the app's hub files at the same time:

- **Phase A (delivered here):** the translation layer (`chatmon/i18n.py`), the template and the test that keeps it
  up to date, and the user-facing strings of every module except M7's.
- **Phase B (after M7 merges):** `app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`, `asking.py`,
  `commands.py` and `settings.py`. Its task is in the ledger, blocked on M7's merge; the coordinator resumes M8
  then. The [list below](#phase-b-the-m7-owned-files) is where to start.

The finding was re-checked on `cac0047` and is real ([findings-recheck.log](reports/m8/findings-recheck.log)). The
decisions on the requirements' gaps are in [readiness.md](reports/m8/readiness.md).

### Design

**Marking a string.** Modules import from `chatmon/i18n.py`:

| Call | For |
|---|---|
| `_("Couldn't open {file}.").format(file=name)` | a whole sentence; values go in named placeholders |
| `ngettext("{n} note", "{n} notes", n).format(n=n)` | a sentence with a count, never `"s" if n != 1` |
| `join(items)` / `either(items)` | "a, b and c" / "“Yes” or “No”" in a sentence |
| `N_("…")` | a string in a table built at import, translated where it's shown with `_(value)` |

**A translation** is `chatmon/locale/<lang>.po` (`de.po`, `pt_BR.po`), copied from the template
`chatmon/locale/chatmon.pot`. Chatmon reads the `.po` file itself: `read_po` parses it, builds a GNU `.mo` in
memory and hands it to the standard library's `gettext.GNUTranslations`, which does the lookups and plural
formulas. There's no build step and nothing generated to commit. An entry that's fuzzy, empty, obsolete, missing
a plural form, or names a placeholder its English doesn't have is left out, so English shows in its place. A file
that isn't `.po`, isn't UTF-8, or has a plural formula gettext refuses counts as not there.

**Choosing the language.** `i18n.setup(choice)` runs once, at start, before any window is built:

1. the person's choice (the `language` setting), if set;
2. otherwise the system's preferred languages in order, the first that has a translation; an English one met
   first stops there. Qt's `uiLanguages()` when Qt is loaded; without Qt (the command line), Windows' own list
   (`GetUserPreferredUILanguages`), or `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` and `LANG` elsewhere;
3. otherwise English.

Then:

- Qt's own translation (`qtbase_<lang>.qm`, which Qt ships) is installed, so its dialogs' buttons follow.
- `localefmt.follow(language)` makes `localefmt.language()`, and so the offline phrases and help, follow.
- A chosen language becomes Qt's default `QLocale`, so times and dates follow it, unless it's the system's own
  language: English chosen on a British system keeps day-month dates. Without a choice, times and dates keep the
  system's regional format.
- `reset()` undoes all of it, which the tests use.

**The template and its gate.** `packaging/extract_strings.py` reads `chatmon/*.py` with `ast` and writes the
template. It records translators' comments (`# Translators: …` just above a call) and flags brace-format strings.
References name the file only, so the template changes when strings do, not when code moves. It stops, naming
file and line, at a string that couldn't be translated:

- an f-string, `+` or `.format()` inside `_()`;
- `_()` or `ngettext()` run at import (module level, class bodies, defaults, decorators);
- a function that uses `_` as a throwaway and calls `_()`;
- one English sentence marked with two different plurals.

`tests/test_i18n.py` fails when the template isn't what the code says, so a new string can't slip in untranslatable.

### Reuse

These were extended in place:

- `localefmt.language()` (M5) gained `follow()`; `offline.phrases()` already asked it, so the phrases follow
  the UI's language with no change to `offline.py`'s loader.
- `companions.Companion` and `styles.Style` keep their English as `label_en` (and `nickname_en`), with `label`
  and `nickname` as properties that translate. Callers in M7's files get the translation without changing.
- The existing `ValueError`, `AgentError`, `BrainError`, `AttachError`, `BackupError` and `KeychainError`
  messages became templates; their English is unchanged, and so are the tests that read them.

New code has a responsibility of its own: `i18n.py` is the one place a language is chosen and strings are looked
up, and the extractor is a development tool beside `packaging/make_icons.py`. Nothing new is a runtime dependency:
`gettext`, `ast`, `ctypes` and Qt's `QTranslator` were all there.

### Not translated

- Logs and stderr diagnostics, config keys, command-line flags, protocol and API names, product and model names.
- The offline commands' phrases and help, which are M5's per-language data in `chatmon/phrases/`.
- Anything sent to a brain: system prompts, transcripts, the attachment framing.
- `releasecheck.py` and `changelog.py`: root's update check loads them from a fixed list
  (`packaging/linux/verify-update`), and translations would widen what root loads. Release notes are an English
  document.
- `report.py`'s issue body, which is for the maintainer.
- `presence.quiet()`'s reasons, which nothing shows.
- `localefmt`'s plain-English fallback.
- Decimal separators ("1.5 MB"); units go through templates, so a translation can say "Mo".

### Strings wrapped in phase A

372 strings (15 with plurals) in 24 modules, from 400 marked calls:

| Module | Strings | | Module | Strings |
|---|---|---|---|---|
| brains.py | 64 | | companions.py | 10 |
| agents.py | 41 | | heads_up.py | 10 |
| updates.py | 34 | | wintoast.py | 9 |
| offline.py | 32 | | chats.py | 8 |
| bubble.py | 28 | | styles.py | 6 |
| reminders.py | 27 | | shortcutportal.py | 5 |
| backup.py | 23 | | richtext.py | 4 |
| attachments.py | 22 | | i18n.py, memory.py, penguin.py | 3 each |
| keychain.py | 21 | | a11y.py, macnative.py | 2 each |
| hotkey.py | 18 | | autostart.py, winuia.py | 1 each |

Modules with no user-facing strings, or only the kinds above, are unchanged. English output changed in three
places, all intended:

- **Cline's disconnect message** now says "removed 1 hook script" for one (it removes three in practice).
- **The exported chat's date line** is written by `localefmt.date_and_time`, as M5's integration notes asked for
  `chats.py`: "Wednesday, November 11, 2026, 3:04 PM" in plain English, the locale's way otherwise.
- **The chat list's "today 3:04 PM" and "Mon Nov 10"** come from `localefmt` too, so they follow the locale. Their
  plain English is the same as before.

## Verification

Run on Windows 11 with Python 3.14.10, PyQt6 6.11.0 (Qt 6.11.2), pytest 9.2.0, ruff 0.17.4 and mypy 2.4.1. The
observation is in [reports/m8/context.log](reports/m8/context.log).

| Check | Command | Result |
|---|---|---|
| M8 tests | `python -m pytest -q -p no:cacheprovider tests/test_i18n.py` | 34 passed ([i18n.log](reports/m8/i18n.log)) |
| Whole suite | `python -m pytest -q -p no:cacheprovider` | 1128 passed, 145 skipped ([suite.log](reports/m8/suite.log)), with the 34 new tests; the coordinator's count for `cac0047` was about 1090 passed (not re-measured here). The 23 warnings are unclosed-socket ResourceWarnings, which pyproject.toml shows rather than fails. |
| Package data | `python -m pytest -q -p no:cacheprovider tests/test_package_data.py` | 2 passed, 3 skipped: those check a built wheel and sdist, which CI builds ([package-data.log](reports/m8/package-data.log)) |
| Lint, types, template | `ruff check .`; `python -m mypy --platform win32` (and `linux`, `darwin`); `python packaging/extract_strings.py --check` | Clean, no mypy issues in 67 files on any platform, template current ([gates.log](reports/m8/gates.log)) |
| Red drills | `python tests/drills/run.py docs/delivery/reports/m8/drill-spec.json --log docs/delivery/reports/m8/drills.log`, and the same for `drill-spec-english.json` into `drills-english.log` | 25 of 25 went green, then red (exit 1, failing in the named test for the intended reason), then green again with the file's bytes restored ([drills.log](reports/m8/drills.log), [drills-english.log](reports/m8/drills-english.log)) |
| Linux (WSL Arch, Python 3.14.9, PyQt6 6.12.1) | the M8 tests and the modules' own, under `LANG=en_US.UTF-8` | 486 passed, 19 skipped ([linux-wsl.log](reports/m8/linux-wsl.log)) |

The Linux run checks the environment-variable path of the language choice, and that a PyQt6 wheel on Linux
ships Qt's translations. It's an extra observation, not a receipt; CI's Linux and macOS legs are the real ones.

The ledger's readiness and resume validations pass. Closure fails only on `T4-wrap-b` and `M8-01.A9`, phase B, as
it must until M7 merges ([validate-readiness.log](reports/m8/validate-readiness.log),
[validate-resume.log](reports/m8/validate-resume.log), [validate-closure.log](reports/m8/validate-closure.log)).
Phase A ends in the ledger's checkpoint.

## Integration notes

### The API phase B and M7 use

| Call | What it does |
|---|---|
| `i18n.setup(choice=None)` | Chooses the language and returns it ("en", "de", "pt_BR"). Call once, after the `QApplication` exists and before any window is built. `choice`: the `language` setting; None or "" follows the system. |
| `i18n._`, `i18n.ngettext`, `i18n.N_` | Look up a string in the chosen language. |
| `i18n.join(items)`, `i18n.either(items)` | Join a list, or a set of choices, into a sentence. |
| `i18n.language()` | The language chosen: "en" until `setup` runs. |
| `i18n.available()` | "en", then each shipped translation's code: what the settings window offers. |
| `i18n.SETTING` | "language", the config key. |
| `i18n.reset()` | Back to English (tests). |

Language names for a menu come from Qt: `QLocale(code).nativeLanguageName()`.

### What M7 (or phase B) must wire

1. **The setting.** Add `"language": ""` to `settings.DEFAULTS`, and to the config template:
   `# The language Chatmon speaks: a code such as "de" or "pt_BR". Empty: your system's.` Then `language = ""`.
2. **Start.** In `app.run()`, once the `QApplication` exists and the config is read, and before `Companion`
   builds a window: `i18n.setup(config.get("language") or None)`. `Companion.__init__` reads the config itself
   today, so either read it earlier in `run()`, or call `setup` at the top of `__init__`, right after
   `_load_config()` and before the stage or any widget.
3. **Command line.** In `cli.main()`, before printing anything: `i18n.setup(language)`, with the setting if it's
   cheap to read there, else `i18n.setup()`. It doesn't load Qt.
4. **Settings window.** Add a Language list: "System default" (""), then `i18n.available()` with
   `QLocale(code).nativeLanguageName()`. A change takes effect at the next start, so say so beside it.
5. **The other language's phrases (M0, M5).** `commands.Table(offline.phrases().commands)` takes the chosen
   language's phrases, keyed by command id, now that `offline.phrases()` follows `i18n.setup`.

### Phase B: the M7-owned files

Wrap every user-facing string in the eight files, with whole-sentence templates. These places in other modules
were left as they are, because their other end is in an M7-owned file and changing one end alone would break the
sentence:

| Where | Why, and what to do |
|---|---|
| `winfiles.Dropped.problem` ("is too big (5 MB)") and `app.py`'s `f"{item.name} {item.problem}"` | A fragment after a file's name. Make `problem` the whole sentence with `{file}`, and have `app.py` show it as it is (`tests/test_winfiles.py` expects the fragments today). |
| `richtext.TURN` ("You:") and its "Attached:" check, and `app.py`'s transcript labels (`**You:**`, `*Attached: …*`) | `richtext` finds a turn by its English label. Translate both ends together, or mark turns some other way. |
| `app.py` 1910 and 1989: `label.split(' (')[0].lower()` on a bubble style's label | String surgery on a translated label. Give the short name a msgid of its own. |
| `app.py` 995: `self._companion().label.lower()` in `brains.system_prompt` | The label now translates; pass `label_en`, so the prompt stays English. |
| `app.py` 1404: `if "metered" in how:` and 1417: `why.startswith("The update")` | They read `updates.py`'s English messages, now translated. Give `updates` a flag, or a kind on `failed`, instead of words. |
| `app.py` 1994 and `menus.py` 244: `f"{b.label} ({b.why_not()})"` | Use a template, `_("{brain} ({reason})")`. |
| `cli.py` 142 and 221, `menus.py` 299-303: `agent.status()` printed raw, `" (installed but off)"` built | Show `agents.status_words(state)`, in a template. |
| `commands.status_lines`: `"- Reminder in 5 min: stretch"` | `reminders.describe` gives a translated phrase ("in 5 min"); put it in a template, `_("Reminder {when}: {text}")`. |
| `keychain.where()` and the reasons from `keychain.set`/`delete` | They give a noun phrase and a lower-case clause. Settings should put them in whole-sentence templates. |
| `asking.py`'s `failed(str)` and the wording `app.py` adds around brain errors | `brains.py`'s side is translated; the rest is phase B. |

### For the coordinator

- **Packaging.** Nuitka's Windows build passes `--noinclude-qt-translations` (`packaging/build.py`). While only
  English ships that's right. When a language ships, include its `qtbase_<lang>.qm`, or Qt's buttons stay
  English in the installed app. PyInstaller's and Nuitka's package-data rules already take `chatmon/locale/*`.
- **Line endings.** Some files edited here were written with LF on Windows. `core.autocrlf=true` normalizes them
  in the index, so the diff shows content only.

## Changelog notes

These describe what M8 phase A's code does. Items that need M7's or phase B's wiring before people see them are
marked **(M7)**.

- Chatmon can be translated. Every word it shows comes from a translation when there's one for your language.
  Only English ships so far, and a new language is a single file.
- Chatmon speaks your system's language when it has a translation for it, or the language you pick in Settings.
  **(M7)**
- Qt's own buttons and menus, in Chatmon's windows, speak the same language. **(M7)**
- An exported chat's date, and the times in the list of chats, follow your system's way of writing times and dates.
- "1 hook script" instead of "1 hook scripts" when disconnecting Cline.

## README notes

**Translation.** Every word Chatmon shows can be translated. A translation is one file,
`chatmon/locale/<language>.po` (for example `de.po` or `pt_BR.po`), made from the template `chatmon.pot` beside
it with any gettext editor. Chatmon uses the first of your system's languages that it has a translation for, or
the one you choose with `language = "de"` in config.toml (and in Settings) **(M7)**. Times and dates follow your
system's regional format, or the language you choose. Only English ships so far. The offline commands' phrases
translate separately, in `chatmon/phrases/`. CONTRIBUTING.md says how to add a translation.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M8",
    "title": "Translation plumbing",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "cac0047"
      },
      {
        "path": "pyproject.toml",
        "revision": "wave3/m8"
      }
    ],
    "inputs": [
      "docs/delivery/m0-app-core.md",
      "docs/delivery/m5-reminders-offline-locale.md",
      "tests/conftest.py",
      "tests/drills/run.py",
      "tests/test_package_data.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "Qt": "6.11.2",
        "ruff": "0.17.4",
        "mypy": "2.4.1"
      }
    }
  },
  "requirements": [
    {
      "id": "M8-01",
      "statement": "Every user-facing string can be translated: gettext with ngettext for plurals, whole-sentence templates instead of fragments, Qt's own translations loading, only English shipped, and a language added as one .po file",
      "priority": "critical",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A2",
        "M8-01.A3",
        "M8-01.A4",
        "M8-01.A5",
        "M8-01.A6",
        "M8-01.A7",
        "M8-01.A8",
        "M8-01.A9"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "M8-01.A1",
      "requirement": "M8-01",
      "given": "Strings marked for translation, before a language is chosen or with none for the person's language",
      "when": "They are shown, counted, listed or given as choices",
      "then": "Each is its English source: ngettext uses English's singular for 1, join gives \"a, b and c\", either \"a or b\", and every module's English output is as before but for the three changes the plan names (the whole suite passes with its expected English untouched)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A2",
      "requirement": "M8-01",
      "given": "A German catalog, written in the test's folder, translating the ask box's Stop, its busy line, and the backup summary's words and plurals",
      "when": "i18n.setup chooses German and the ask box is built and a backup summarised",
      "then": "The ask box and the summary show the German, with the right plural form and list joining, and strings the catalog leaves out show in English",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A3",
      "requirement": "M8-01",
      "given": "A catalog with fuzzy, empty, obsolete, incomplete-plural and wrong-placeholder entries, or a file that isn't .po, isn't UTF-8 or has a plural formula gettext refuses",
      "when": "It is chosen",
      "then": "Each of those entries shows in English, never a hole or an exception, and a file that can't be read counts as not there: English",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A4",
      "requirement": "M8-01",
      "given": "The person's choice, or the system's preferred languages, and translations for some languages",
      "when": "The language is chosen",
      "then": "The person's choice wins; else the first preferred language with a translation (region, then language: pt-BR is pt_BR.po then pt.po); an English one first means English; what isn't a language tag never names a file; and the command line reads the same first preference as Qt",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A5",
      "requirement": "M8-01",
      "given": "A language chosen by i18n.setup",
      "when": "localefmt and the offline phrases are asked for the person's language, then i18n.reset runs",
      "then": "localefmt.language() is the chosen language and offline.phrases() loads that language's phrases; after reset both are as before",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A6",
      "requirement": "M8-01",
      "given": "Qt's own translations installed, and a QApplication",
      "when": "A language other than the system's is chosen, then reset; or the system's own language is chosen",
      "then": "Qt's own words (QPlatformTheme's Cancel) are translated and the default QLocale is the chosen language, so times follow it; reset puts both back; choosing the system's own language leaves the default locale (its regional formats) alone",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A7",
      "requirement": "M8-01",
      "given": "The code's marked strings",
      "when": "The template is generated and checked",
      "then": "chatmon.pot is exactly what the extractor writes and reads as a catalog; --check exits 1 when it's out of date and 2 for a string that couldn't be translated (an f-string, +, .format() inside _(), a translation run at import, a throwaway _ beside _(), one sentence with two plurals), while strings translated at run time pass",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A8",
      "requirement": "M8-01",
      "given": "The repository's tracked files under chatmon/",
      "when": "The package data globs are read as setuptools reads them",
      "then": "The template, and any translation beside it, ship in the wheel and sdist through locale/*",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M8-01.A9",
      "requirement": "M8-01",
      "given": "The eight M7-owned files (app, settingswin, cli, menus, messages, asking, commands, settings)",
      "when": "Phase B wraps their strings, with the integration notes' cross-file fragments",
      "then": "Their user-facing strings go through i18n as whole-sentence templates and the English output is unchanged",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T1-layer",
      "purpose": "Add chatmon/i18n.py (gettext lookups, .po reading, the language choice, Qt's translation, the default locale) and localefmt.follow, with tests/test_i18n.py",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A3",
        "M8-01.A4",
        "M8-01.A5",
        "M8-01.A6"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/i18n.py",
          "action": "create"
        },
        {
          "path": "chatmon/localefmt.py",
          "action": "modify"
        },
        {
          "path": "tests/test_i18n.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-i18n",
        "E-suite",
        "E-red-M8-01-fuzzy-used",
        "E-red-M8-01-placeholder-unchecked",
        "E-red-M8-01-english-not-first",
        "E-red-M8-01-region-dropped",
        "E-red-M8-01-windows-languages-unread",
        "E-red-M8-01-localefmt-not-following",
        "E-red-M8-01-setup-not-telling-localefmt",
        "E-red-M8-01-qt-translation-not-installed",
        "E-red-M8-01-chosen-locale-not-default",
        "E-red-M8-01-default-locale-not-restored",
        "E-red-M8-01-system-language-overrides-region",
        "E-red-M8-01-english-list-broken"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T2-template",
      "purpose": "Add the ast extractor that writes chatmon/locale/chatmon.pot and refuses untranslatable strings, ship locale/* as package data, and say how in CONTRIBUTING.md",
      "acceptance": [
        "M8-01.A7",
        "M8-01.A8"
      ],
      "depends_on": [
        "T1-layer"
      ],
      "changes": [
        {
          "path": "packaging/extract_strings.py",
          "action": "create"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "action": "create"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "CONTRIBUTING.md",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-i18n",
        "E-suite",
        "E-package-data",
        "E-gates",
        "E-red-M8-01-check-passes-stale",
        "E-red-M8-01-import-time-allowed",
        "E-red-M8-01-throwaway-allowed",
        "E-red-M8-01-fstring-allowed",
        "E-red-M8-01-comprehension-scope-lost",
        "E-red-M8-01-locale-not-shipped"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T3-wrap-a",
      "purpose": "Wrap the user-facing strings of every module but M7's in whole-sentence templates, ngettext plurals and join lists, English unchanged, and keep the template current",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A2",
        "M8-01.A7"
      ],
      "depends_on": [
        "T1-layer",
        "T2-template"
      ],
      "changes": [
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "chatmon/attachments.py",
          "action": "modify"
        },
        {
          "path": "chatmon/autostart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/backup.py",
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
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/companions.py",
          "action": "modify"
        },
        {
          "path": "chatmon/heads_up.py",
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
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/memory.py",
          "action": "modify"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "chatmon/richtext.py",
          "action": "modify"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "action": "modify"
        },
        {
          "path": "chatmon/styles.py",
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
          "path": "chatmon/winuia.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-i18n",
        "E-suite",
        "E-red-M8-01-gettext-bypassed",
        "E-red-M8-01-plural-english-only",
        "E-red-M8-01-list-and-in-english",
        "E-red-M8-01-ui-string-not-wrapped",
        "E-red-M8-01-plural-glued",
        "E-red-M8-01-template-stale",
        "E-red-M8-01-english-sentence-changed"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T4-wrap-b",
      "purpose": "Phase B: wrap the M7-owned files' strings and fix the cross-file fragments listed in the integration notes",
      "acceptance": [
        "M8-01.A9"
      ],
      "depends_on": [
        "T3-wrap-a"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/messages.py",
          "action": "modify"
        },
        {
          "path": "chatmon/asking.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        }
      ],
      "status": "blocked",
      "evidence": [],
      "blocker": "M7 (wave 2) is changing these files now; the coordinator resumes M8 for phase B once M7 merges",
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-readiness",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A2",
        "M8-01.A3",
        "M8-01.A4",
        "M8-01.A5",
        "M8-01.A6",
        "M8-01.A7",
        "M8-01.A8",
        "M8-01.A9"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of M8-01 against the assessment, the roadmap's owner decisions (translation plumbing with only English shipped; no new runtime dependencies), M5's and M0's integration notes and the wave-3 brief: the finding re-checked on cac0047 (findings-recheck.log), ambiguities resolved with recorded decisions D1-D13, failure behaviour, terminology, scope (phases A and B) and coverage (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m8/readiness.md",
        "sha256": "90a0075b58de8287552aeb3bd1d861049a77e701fd19a3bb0e704e27224cbba3"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "0e6b3c0248e1a69b43b84912b764e7670256508f4d44d1ae27238ac2dd20a8e7",
      "red": null,
      "reason": null
    },
    {
      "id": "E-i18n",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A2",
        "M8-01.A3",
        "M8-01.A4",
        "M8-01.A5",
        "M8-01.A6",
        "M8-01.A7"
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
        "-rs",
        "tests/test_i18n.py"
      ],
      "method": "Ran tests/test_i18n.py: 34 passed. Real gettext catalogs written as .po files in each test's own folder, a real AskBox and backup summary under the offscreen Qt platform, Qt's own qtbase_de.qm, a subprocess without Qt for the command line's languages, and the extractor run on sources and on a throwaway project.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/i18n.log",
        "sha256": "8489b41dbf01f5405f6b6b896153d80b96172b73effff8c8e73674631892d2c1"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": null,
      "reason": null
    },
    {
      "id": "E-suite",
      "acceptance": [
        "M8-01.A1",
        "M8-01.A2",
        "M8-01.A3",
        "M8-01.A4",
        "M8-01.A5",
        "M8-01.A6",
        "M8-01.A7",
        "M8-01.A8"
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
      "method": "Ran the whole suite on the final tree with the template and every change staged: 1128 passed, 145 skipped. Every existing test's expected English is unchanged, so every module's English output is as before; the new tests are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/suite.log",
        "sha256": "33a87e71cc857d8eecc0fb80f916d457f7ce7a5d1c2356e30384e3cb825f8b05"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": null,
      "reason": null
    },
    {
      "id": "E-package-data",
      "acceptance": [
        "M8-01.A8"
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
        "-rs",
        "tests/test_package_data.py"
      ],
      "method": "Ran M6A's package-data tests, which read pyproject.toml's globs as setuptools does and hold them against git's tracked files: 2 passed (the template is taken by locale/*, and every glob takes a file), 3 skipped (they check a built wheel and sdist, which CI's packages workflow builds).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/package-data.log",
        "sha256": "633d9c56c18bdbb036a72e0f9fd943a71c4c2a442f68e4bdff75944819bfe0d7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "9f7d765005cd04349d42958b0857da6512e95b805def156a78066b42eed66717",
      "red": null,
      "reason": null
    },
    {
      "id": "E-gates",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "packaging/extract_strings.py",
        "--check"
      ],
      "method": "Ran ruff check ., mypy on win32, linux and darwin (chatmon/i18n.py is checked; 67 source files, no issues) and the template check (exit 0: chatmon.pot is what the code says), each logged with its exit code in gates.log.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/gates.log",
        "sha256": "453b2bcc2ad0eabb386e21f4bd6bafa51f4a52d1d6de2ca03e04cfc9cdb33cdf"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": null,
      "reason": null
    },
    {
      "id": "E-red-M8-01-gettext-bypassed",
      "acceptance": [
        "M8-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-gettext-bypassed in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'return _catalog.gettext(message)' -> 'return message'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english",
        "observed_diagnostic": "_ test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english _",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "3fccbe283ba1f5394a99e1c726f5b8422b5e4f0b25f1010c6b68cb9d953f44df"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-plural-english-only",
      "acceptance": [
        "M8-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-plural-english-only in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'return _catalog.ngettext(singular, plural, n)' -> 'return singular if n == 1 else plural'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english",
        "observed_diagnostic": "_ test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english _",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "5af45f9ecc1dfbb494e1ea182b09b442065298d9bdc19dcd4c532c5ed68668d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-list-and-in-english",
      "acceptance": [
        "M8-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-list-and-in-english in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'text = _(\"{list} and {last}\").format(list=text, last=listed[-1])' -> 'text = \"{list} and {last}\".format(list=text, last=listed[-1])'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english",
        "observed_diagnostic": "_ test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english _",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "d039dd0bf82338937f277eeb510a53d16b5be5e1b621860c7bcc04d670f943a3"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-ui-string-not-wrapped",
      "acceptance": [
        "M8-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-ui-string-not-wrapped in a temporary copy (tests/drills/run.py): green, then chatmon/bubble.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'self.stop_button = QToolButton(text=_(\"Stop\"), autoRaise=True)' -> 'self.stop_button = QToolButton(text=\"Stop\", autoRaise=True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english",
        "observed_diagnostic": "_ test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english _",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "6273b5d4c70845c166559073b3c1fbe6b571c99f5f4b6e8f9098cac50ba1ab0d"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-plural-glued",
      "acceptance": [
        "M8-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-plural-glued in a temporary copy (tests/drills/run.py): green, then chatmon/backup.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'parts.append(ngettext(\"{n} note\", \"{n} notes\", len(self.notes)).format(n=len(self.notes)))' -> 'parts.append(f\"{len(self.notes)} note{\\'s\\' if len(self.notes) != 1 else \\'\\'}\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english",
        "observed_diagnostic": "_ test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english _",
        "before": [
          {
            "path": "chatmon/backup.py",
            "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/backup.py",
            "sha256": "8b151536ac19605c184d3fa848768bab55bcaaedcc08e8d5cacabe1caebcfb41"
          }
        ],
        "after": [
          {
            "path": "chatmon/backup.py",
            "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-fuzzy-used",
      "acceptance": [
        "M8-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-fuzzy-used in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'    if e.fuzzy:' -> '    if e.fuzzy and False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_slip_in_a_translation_shows_english_and_never_a_hole",
        "observed_diagnostic": "_________ test_a_slip_in_a_translation_shows_english_and_never_a_hole _________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "3fa8c9d9de7efed512e4e3f09c67f6040859a2bf3f220ff29f75d65012f3e0d9"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-placeholder-unchecked",
      "acceptance": [
        "M8-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-placeholder-unchecked in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'if names is None or not names <= english:' -> 'if names is None:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_slip_in_a_translation_shows_english_and_never_a_hole",
        "observed_diagnostic": "_________ test_a_slip_in_a_translation_shows_english_and_never_a_hole _________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "3aacb9ca0ac1c615bad048adc418f2e74afd59d1f2feb009e377809aee8e0845"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-english-not-first",
      "acceptance": [
        "M8-01.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-english-not-first in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'            if code == SOURCE:' -> '            if code == \"zz\":'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_language_is_the_persons_choice_else_the_first_preferred_one_with_a_translation",
        "observed_diagnostic": "_ test_the_language_is_the_persons_choice_else_the_first_preferred_one_with_a_translation _",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "9ca5fad2e4f4394e0a46d9cf15de054ffd1d7b6de9b20dad504f6e1c9ca90b3b"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-region-dropped",
      "acceptance": [
        "M8-01.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-region-dropped in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'names = [f\"{lang}_{region.upper()}\"] if region else []' -> 'names = []'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_language_is_the_persons_choice_else_the_first_preferred_one_with_a_translation",
        "observed_diagnostic": "_ test_the_language_is_the_persons_choice_else_the_first_preferred_one_with_a_translation _",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "689ecfcf348b284f38b4064241546da528ef7276bf677d5c2019d96c5d4f4495"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-windows-languages-unread",
      "acceptance": [
        "M8-01.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-windows-languages-unread in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'return [name for name in ctypes.wstring_at(names, size.value).split(\"\\\\0\") if name]' -> 'return []'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_command_line_reads_the_same_preferred_languages_as_qt",
        "observed_diagnostic": "_______ test_the_command_line_reads_the_same_preferred_languages_as_qt ________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "bc3e54eb988863a8ad90616bdb29389398a26cedf4bc82ad4099afbfcdb73a9c"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-localefmt-not-following",
      "acceptance": [
        "M8-01.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-localefmt-not-following in a temporary copy (tests/drills/run.py): green, then chatmon/localefmt.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'        return _shown_in' -> '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_localefmt_and_the_offline_phrases_follow_the_language_chosen",
        "observed_diagnostic": "______ test_localefmt_and_the_offline_phrases_follow_the_language_chosen ______",
        "before": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "33ee339ce497b2f378ca95ecfe26d7b6d53d77abb1ede7074ad1aefec5825dbb"
          }
        ],
        "after": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-setup-not-telling-localefmt",
      "acceptance": [
        "M8-01.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-setup-not-telling-localefmt in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'localefmt.follow(_language)' -> 'localefmt.follow(None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_localefmt_and_the_offline_phrases_follow_the_language_chosen",
        "observed_diagnostic": "______ test_localefmt_and_the_offline_phrases_follow_the_language_chosen ______",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "07269aea43428f115f9e1a7e72de9763e2ed9a455ce52cc77243e6a77a464fae"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-qt-translation-not-installed",
      "acceptance": [
        "M8-01.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-qt-translation-not-installed in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'and app.installTranslator(translator):' -> 'and False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_qts_own_words_and_a_chosen_languages_dates_follow_it",
        "observed_diagnostic": "__________ test_qts_own_words_and_a_chosen_languages_dates_follow_it __________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "09a9c83ff9bf8d4f030a3961110ce886680942f9d27d7f115b8aeac734e8e3ce"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-chosen-locale-not-default",
      "acceptance": [
        "M8-01.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-chosen-locale-not-default in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'qtcore.QLocale.setDefault(wanted)' -> 'qtcore.QLocale(wanted)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_qts_own_words_and_a_chosen_languages_dates_follow_it",
        "observed_diagnostic": "__________ test_qts_own_words_and_a_chosen_languages_dates_follow_it __________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "a6b62f9ca19339e83651e8fd5633470304be618a88ca55cea3e0bd1d40cc0b6d"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-default-locale-not-restored",
      "acceptance": [
        "M8-01.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-default-locale-not-restored in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'qtcore.QLocale.setDefault(_default_before)' -> 'qtcore.QLocale(_default_before)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_qts_own_words_and_a_chosen_languages_dates_follow_it",
        "observed_diagnostic": "__________ test_qts_own_words_and_a_chosen_languages_dates_follow_it __________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6447bcb97b9aac3b84582b8786980d0dc3e6da40712c2fc9821480fc14277ab2"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-system-language-overrides-region",
      "acceptance": [
        "M8-01.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-system-language-overrides-region in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "8f5f3a62757159a757c11d4e23b71a3d064a406171dd48f79cc5fee4c77090b5",
      "red": {
        "mutation": "'if wanted.language() != qtcore.QLocale.system().language():' -> 'if True:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_choosing_the_systems_own_language_keeps_its_regional_formats",
        "observed_diagnostic": "______ test_choosing_the_systems_own_language_keeps_its_regional_formats ______",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "f389d00184b7101cf67f8a8a91bdf10ed668665e2439dea5f767541e445a7b8c"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-template-stale",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-template-stale in a temporary copy (tests/drills/run.py): green, then chatmon/memory.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'return _(\"There\\'s nothing there to remember.\")' -> 'return _(\"There\\'s nothing there to remember!\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_template_has_every_marked_string_and_reads_as_a_catalog",
        "observed_diagnostic": "______ test_the_template_has_every_marked_string_and_reads_as_a_catalog _______",
        "before": [
          {
            "path": "chatmon/memory.py",
            "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/memory.py",
            "sha256": "72ecdb69f5cef1066605e8092172f2e5345b9caaa51388eeda48c9784950b13f"
          }
        ],
        "after": [
          {
            "path": "chatmon/memory.py",
            "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-check-passes-stale",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-check-passes-stale in a temporary copy (tests/drills/run.py): green, then packaging/extract_strings.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'            return 1' -> '            return 0'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_template_check_fails_when_a_string_is_added_without_it",
        "observed_diagnostic": "_______ test_the_template_check_fails_when_a_string_is_added_without_it _______",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "acf0367b6a6076d00311fe729c4243ca74e67cc8e9b1231a3789a5230a6406a3"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-import-time-allowed",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-import-time-allowed in a temporary copy (tests/drills/run.py): green, then packaging/extract_strings.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'if marker in TRANSLATED_NOW and at_import:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_extractor_refuses_a_string_that_couldnt_be_translated",
        "observed_diagnostic": "_ test_the_extractor_refuses_a_string_that_couldnt_be_translated[GREETING = _(\"Hi\")\\n-imported] _",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "38e389249bbd267dabc87fe0d2bbe8127ad1a3be11e0719eb82b7d7b9e047140"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-throwaway-allowed",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-throwaway-allowed in a temporary copy (tests/drills/run.py): green, then packaging/extract_strings.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'if binds and translated_here:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_extractor_refuses_a_string_that_couldnt_be_translated",
        "observed_diagnostic": "_ test_the_extractor_refuses_a_string_that_couldnt_be_translated[def f(pairs):\\n    for _, b in pairs:\\n        print(_(\"Hi\"))\\n-throwaway] _",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "f9259f9ad1596cb922a23f907cc528be3c540c6b25069502099c07e6328f9d78"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-fstring-allowed",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-fstring-allowed in a temporary copy (tests/drills/run.py): green, then packaging/extract_strings.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'elif marker == \"_\" and isinstance(texts[0], (ast.Name, ast.Attribute, ast.Subscript)):' -> 'elif marker == \"_\" and isinstance(texts[0], (ast.Name, ast.Attribute, ast.Subscript, ast.JoinedStr)):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_extractor_refuses_a_string_that_couldnt_be_translated",
        "observed_diagnostic": "_ test_the_extractor_refuses_a_string_that_couldnt_be_translated[def f(x):\\n    return _(f\"Hi {x}\")\\n-plain string literals] _",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "bde6a4b2347270e46da55552482807876e9b8f91136ddb24a52f5ca28d08bee4"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-comprehension-scope-lost",
      "acceptance": [
        "M8-01.A7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-comprehension-scope-lost in a temporary copy (tests/drills/run.py): green, then packaging/extract_strings.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_extractor_lets_be_what_runs_later_and_throwaways_elsewhere",
        "observed_diagnostic": "_____ test_the_extractor_lets_be_what_runs_later_and_throwaways_elsewhere _____",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "5ebab72db377b088cca322f45f243a43b184c94f0107f794f42116c610453f30"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-locale-not-shipped",
      "acceptance": [
        "M8-01.A8"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec.json",
        "--log",
        "docs/delivery/reports/m8/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-locale-not-shipped in a temporary copy (tests/drills/run.py): green, then pyproject.toml mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills.log",
        "sha256": "24b23e20d92b970395e95d1d17c4def093eab7bed1f5ffa476396ad08c261bb7"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "9f7d765005cd04349d42958b0857da6512e95b805def156a78066b42eed66717",
      "red": {
        "mutation": "'    \"locale/*\",  # the template, and each translation (.po) beside it: adding a language adds a file and nothing here' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_every_tracked_file_of_chatmon_ships",
        "observed_diagnostic": "__________________ test_every_tracked_file_of_chatmon_ships ___________________",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "1346bff36c7358951bc5619845cf6ab83c00cb7cab8da74e7a98195b720d9611"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-english-list-broken",
      "acceptance": [
        "M8-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec-english.json",
        "--log",
        "docs/delivery/reports/m8/drills-english.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-english-list-broken in a temporary copy (tests/drills/run.py): green, then chatmon/i18n.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills-english.log",
        "sha256": "9acf316e6adcd212181e7c835c5d0b0b3d2cf51fa255e3cd25f2b5f0350fa9e6"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'    for item in listed[1:-1]:' -> '    for item in listed[1:]:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_before_a_language_is_chosen_every_string_is_its_english",
        "observed_diagnostic": "________ test_before_a_language_is_chosen_every_string_is_its_english _________",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "afdad76154207a2ce1bcb49f83aced2e2f446c47b420d326296d78d27cd0fdac"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M8-01-english-sentence-changed",
      "acceptance": [
        "M8-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m8/drill-spec-english.json",
        "--log",
        "docs/delivery/reports/m8/drills-english.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M8-01-english-sentence-changed in a temporary copy (tests/drills/run.py): green, then chatmon/backup.py mutated once and the named test failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "ruff": "0.17.4",
          "mypy": "2.4.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m8/drills-english.log",
        "sha256": "9acf316e6adcd212181e7c835c5d0b0b3d2cf51fa255e3cd25f2b5f0350fa9e6"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
        },
        {
          "path": "chatmon/companions.py",
          "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
        },
        {
          "path": "chatmon/localefmt.py",
          "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
          "path": "docs/delivery/m0-app-core.md",
          "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
        },
        {
          "path": "docs/delivery/m5-reminders-offline-locale.md",
          "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
        },
        {
          "path": "pyproject.toml",
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
          "path": "tests/test_i18n.py",
          "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
        }
      ],
      "scope_sha256": "122d0d20cd9409139dd4ed9d100a5830437e1dc0a77fa4a7ceea09e76d06317f",
      "red": {
        "mutation": "'    return _(\"Brought back {what}.\").format(what=contents.summary())' -> '    return _(\"Brought back: {what}.\").format(what=contents.summary())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_backup_moves_everything_to_another_computer",
        "observed_diagnostic": "_____________ test_a_backup_moves_everything_to_another_computer ______________",
        "before": [
          {
            "path": "chatmon/backup.py",
            "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/backup.py",
            "sha256": "71fdcc72335d6671a8c8ee31b52731e495215b316792dd7861d8cf7a40d1ab09"
          }
        ],
        "after": [
          {
            "path": "chatmon/backup.py",
            "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "0e6b3c0248e1a69b43b84912b764e7670256508f4d44d1ae27238ac2dd20a8e7",
    "inputs": [
      {
        "path": "CONTRIBUTING.md",
        "sha256": "6761609e7b8262d221582dcf77749cb21a5e0edb20051f0f2d0fdedae6418de2"
      },
      {
        "path": "chatmon/a11y.py",
        "sha256": "0c7bd0b2aac7872b36cfc2631aaf5ccf8bf2c985d739960696acc9980e314cc5"
      },
      {
        "path": "chatmon/agents.py",
        "sha256": "d90e6e6264a8712ec5a46a975755c11612ad5f63f6893189b051771a25410c63"
      },
      {
        "path": "chatmon/app.py",
        "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
      },
      {
        "path": "chatmon/asking.py",
        "sha256": "704082d9fe432fe2fef872b73cf0c0a4a8eb701b6a54924ec45c2d17d22bd088"
      },
      {
        "path": "chatmon/attachments.py",
        "sha256": "424f321616e81051185a9c6335746eb05e1875da0d2deafd22a447037d2ec0e5"
      },
      {
        "path": "chatmon/autostart.py",
        "sha256": "b8b880104834e2d7ab8e1c8f6c28f98f3e134bc8b0823ba0512f3d2bb4517710"
      },
      {
        "path": "chatmon/backup.py",
        "sha256": "02f5871af891098c08f1a8e5f757a5873d428789c44b1734d8ebf7e1088cab33"
      },
      {
        "path": "chatmon/brains.py",
        "sha256": "13fbf719180b54500a48c898352167fd7614d0d0b01d9dea55424ed81c93c427"
      },
      {
        "path": "chatmon/bubble.py",
        "sha256": "2e27bf976ff053b2211667776e448405576631559e219b17902f7cefaadcdf8e"
      },
      {
        "path": "chatmon/chats.py",
        "sha256": "3419a5b4f6872399b2c196dd0e5276b4ba501c0508378401b020d7c135c9e656"
      },
      {
        "path": "chatmon/cli.py",
        "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
      },
      {
        "path": "chatmon/commands.py",
        "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
      },
      {
        "path": "chatmon/companions.py",
        "sha256": "8f9b0cc0b69ca4b302d622dcff5b209a50f6977fcc9ecb270c2be1d916f7d373"
      },
      {
        "path": "chatmon/heads_up.py",
        "sha256": "5569fd769b3a3f82d76e1a8a62b6aa21d2e7d403e8592141414d13ad7dccaa98"
      },
      {
        "path": "chatmon/hotkey.py",
        "sha256": "254785ae31a3fe5483d97e5f8e5455e41e4bd2de6506903528e1e98afc68d435"
      },
      {
        "path": "chatmon/i18n.py",
        "sha256": "654c28afb2996e28f51aa23cba928d30a93b0dba3ae25406c22b5e5dc197c31f"
      },
      {
        "path": "chatmon/keychain.py",
        "sha256": "f650dc29b9eb4e41ceca7c737ba38c6d5bcdbef01cb16292d1c3c9717e66fd73"
      },
      {
        "path": "chatmon/locale/chatmon.pot",
        "sha256": "0b0d23c24b9adfbe9ab6a569db8442918ca5c12e43161c50f6ab8548ff393a5f"
      },
      {
        "path": "chatmon/localefmt.py",
        "sha256": "aa1eeb5485558e74aa7a4e8aa54590d32cd3b5c37cbeb8d06a2f848c3c914250"
      },
      {
        "path": "chatmon/macnative.py",
        "sha256": "96224f733c1ea53ce759fd6e0a3edea1aeed352a4cc4da4322d06fbef9ce43c7"
      },
      {
        "path": "chatmon/memory.py",
        "sha256": "efca4a23bf9c7b5f8ed104156fb38cfc49afe116e2ae69fa413cec6d775878c7"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
      },
      {
        "path": "chatmon/messages.py",
        "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
      },
      {
        "path": "chatmon/offline.py",
        "sha256": "e979cc5339c3d43595583fac20f4ca095a760cc94fd4132433913735826b02a0"
      },
      {
        "path": "chatmon/penguin.py",
        "sha256": "890a726123f29a1fbcf05faf83493fb8af2dded6042c5da7a7cb7a851017516d"
      },
      {
        "path": "chatmon/reminders.py",
        "sha256": "6b467b825705a60eb84d1e1f46b2eaddc1dffe8cf03e5fb30805485bf2ceaf25"
      },
      {
        "path": "chatmon/richtext.py",
        "sha256": "4bbfa336ff0c2d2f10ae726177bab5e4711b733c714678e425ec9f1ab3199715"
      },
      {
        "path": "chatmon/settings.py",
        "sha256": "e4247d3492657f1a53efffc4b7ec4594d5ccee1c77cb9633c55ec80528649f5d"
      },
      {
        "path": "chatmon/settingswin.py",
        "sha256": "c2e61fc6adb7d82bc940d13ce06cd0908a160a74d9f35fe89242ae5dcbe24015"
      },
      {
        "path": "chatmon/shortcutportal.py",
        "sha256": "4f4a14531d55ea20657ed04d19520aa89c12e776094c9292f7154f9db661d7dd"
      },
      {
        "path": "chatmon/styles.py",
        "sha256": "446c8d819d9f5d744b583f81562113221b48fac647c8cc895cc6ae5a2fe3d9d7"
      },
      {
        "path": "chatmon/updates.py",
        "sha256": "9a0448313bc823b8cea1508e7c881ed7b64be2bedb597aa6c2aa15a84207cd68"
      },
      {
        "path": "chatmon/wintoast.py",
        "sha256": "0e1157275f35115c365f746f83a7a6173b0cacd51743d26b2cf1be6a73aa7be8"
      },
      {
        "path": "chatmon/winuia.py",
        "sha256": "2f172902548b3020a6d70c62a2d6fc86a5f2b5f84e9f559fa857cf2f4b7beef6"
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
        "path": "docs/delivery/m0-app-core.md",
        "sha256": "b7567c551c1f1796467ddaf6ed7638e3f665428725b403b62048d6a50ff768fc"
      },
      {
        "path": "docs/delivery/m5-reminders-offline-locale.md",
        "sha256": "5bdaf1789b58e63b13ca52152a85bd0df2b8bb3d03d8b41b35c24fb8c34d67c3"
      },
      {
        "path": "packaging/extract_strings.py",
        "sha256": "8023c6047a81bbadf1d5ddc7b8513c9947d4163644b752aa017e50213303d4d7"
      },
      {
        "path": "pyproject.toml",
        "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
        "path": "tests/test_i18n.py",
        "sha256": "c864fd5bc6323cbd6b8ebec82f70a1562aa42521a8d5b0404b8a92f256eb7d75"
      },
      {
        "path": "tests/test_package_data.py",
        "sha256": "a78baebb59160a9f1c8685cd0d02649177688604192d4aa89875af23f704b47c"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "Qt": "6.11.2",
        "ruff": "0.17.4",
        "mypy": "2.4.1"
      }
    },
    "verified_tasks": [
      "T1-layer",
      "T2-template",
      "T3-wrap-a"
    ],
    "pending_operations": [],
    "next_action": "Phase B, once M7 merges and the coordinator resumes M8 on the merged base: wrap the eight M7-owned files and fix the cross-file fragments listed under Integration notes (Phase B), wire i18n.setup and the language setting, regenerate chatmon/locale/chatmon.pot, then run the suite, the template check and new drills, and close T4-wrap-b. CI's Linux and macOS legs run tests/test_i18n.py on the next push.",
    "source_revision": "ad03c4d4f7ebedb63f2b5091e523a11ed00e5b81"
  }
}
```
