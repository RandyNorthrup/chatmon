# M8 readiness review

Requirements review of assessment item M8-01 against the roadmap's owner decisions ("Translation: plumbing plus
locale formats … Only English ships", "No new runtime dependencies"), M5's integration notes (`localefmt`, the
phrase data, "M8: choose a UI language with `QLocale.setDefault`"), M0's (`commands.Table` takes another
language's phrases) and the coordinator's brief for wave 3. Reviewed on `wave3/m8` from `cac0047`, Windows 11,
Python 3.14.10. The review was written after a first pass over the code, which showed what the decisions had to
cover; every decision below is one the delivered code follows.

## The finding

Re-checked on `cac0047` ([findings-recheck.log](findings-recheck.log)): Chatmon has no translation layer (no
gettext, no `QTranslator`), and builds sentences from fragments and plurals with `'s' if n != 1`. Confirmed. The
assessment's `app.py` line numbers predate M0's split of `app.py`; the sentences they named are now in `app.py`,
`menus.py` and `commands.py`, which M7 owns.

## Scope

M8 runs in two phases, because M7 is changing the hub files at the same time:

- **Phase A (this delivery):** the translation layer, the template and its gate, and every user-facing string in
  every module except the M7-owned files.
- **Phase B (after M7 merges):** `app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`, `asking.py`,
  `commands.py` and `settings.py`. Its task is in the ledger, blocked on M7's merge.

## Ambiguities resolved

| # | Question | Decision |
|---|---|---|
| D1 | .po or .mo, and when compiled? | **.po read at runtime.** `i18n.read_po` parses the file (about 80 lines of standard library), builds a GNU .mo in memory and hands it to `gettext.GNUTranslations`, which does the lookups, contexts and plural formulas. "Adding a language is one .po file" stays literally true: no build step, nothing generated to commit, nothing for packaging to compile. Only the chosen language's file is read, once. |
| D2 | Where do the template and translations live? | `chatmon/locale/chatmon.pot` and `chatmon/locale/<lang>.po`. Package data takes `locale/*`, so adding a language changes no configuration. M6A's package-data test requires each glob to take a tracked file, which the template does. |
| D3 | How is the language chosen? | The person's choice (the `language` setting) if set; otherwise the system's preferred languages in order (Qt's `uiLanguages()`, or without Qt, Windows' own list, or `LANGUAGE`/`LC_ALL`/`LC_MESSAGES`/`LANG`). The first with a translation wins. An English one met first stops the search, since English is the source. A tag is reduced to letters and digits before it names a file, so "../de" or "klingon" never does. |
| D4 | The setting's name | `language` at the top level of config.toml (`i18n.SETTING`): a code such as `"de"` or `"pt_BR"`, empty to follow the system. M7 adds it to `settings.DEFAULTS`, the template and the settings window. |
| D5 | Lazy or explicit choice? | **Explicit:** `i18n.setup(choice)` once, at start, before any window is built. A lazy choice on first use would fix strings in English before the setting is read. Until phase B wires it in `app.py` and `cli.py`, everything shows in English, which is all that ships. |
| D6 | Qt's own translations for which language? | For the language Chatmon itself is shown in, not the system's: a French system with no French translation of Chatmon gets English Qt buttons, not a mixed window. |
| D7 | Times and dates when a language is chosen | A chosen language becomes Qt's default `QLocale` (as M5 asked), unless it's the system's own language: choosing English on a British system keeps its day-month dates. With no choice, formats keep the system's regional format, which is how Windows and macOS separate display language and region. |
| D8 | `localefmt` and the phrases | `i18n.setup` tells `localefmt.follow(language)`; `localefmt.language()` answers with it, and `offline.phrases()` already asks `localefmt.language()`. So help and offline phrases are in the UI's language, not the region's. |
| D9 | A broken translation | Never a crash and never a hole. Fuzzy, empty, obsolete and incomplete plural entries are left out; so is an entry whose translation names a placeholder its English doesn't have (`.format()` would raise). A file that isn't .po, isn't UTF-8 or has a plural formula gettext refuses counts as not there: English. |
| D10 | Strings at import time | `_()` at import would fix the English before the language is chosen. Tables use `N_()` and are translated where shown; the extractor refuses `_()`/`ngettext()` at module level, in class bodies, defaults and decorators. Dataclass tables keep their English in `label_en` and translate in a `label` property, so callers in M7's files get the translation without changing. |
| D11 | Plurals and lists | `ngettext` wherever a count is shown, even where English doesn't change ("{n} min"): other languages do. Lists go through `join()`; choices through `either()`. "every Monday at {time}" is seven sentences, not a day's name inside one, because some languages inflect it. |
| D12 | Not translated | Logs and stderr diagnostics, config keys, flags, protocol and API names, product and model names, the offline commands' phrases (M5's data), anything sent to a brain (system prompts, transcripts, attachment framing). Also: `releasecheck.py` and `changelog.py`, which root's update check loads from a fixed list (`packaging/linux/verify-update`); release notes, which are an English document; `report.py`'s issue body, which is for the maintainer; `presence.quiet()` reasons, which nothing shows; `localefmt`'s plain-English fallback; Qt's "C" locale. |
| D13 | Numbers | Decimal separators keep Python's formatting ("1.5 MB"). Units go through templates ("{size} MB"), so a French translation can say "Mo". A non-goal for now. |

## Failure behaviour

- `setup` never raises for a missing, broken or unreadable translation: English.
- `setup` without a QApplication still chooses the language; Qt's translation is skipped (it needs one).
- Qt's translation files missing (a distribution packages them separately): Qt stays English, Chatmon's own words
  are still translated. The test skips with that reason.
- The extractor exits 2 naming file and line for an untranslatable string, 1 for an out-of-date template.

## Terminology

"Translation" is one `.po` file; "template" is `chatmon.pot`; "the language" is what `setup` chose
(`i18n.language()`); "English" is the source, never a file.

## Coverage

Every acceptance criterion in the ledger has an owning task, a behavior test and at least one red drill. The
phase-B criterion is owned by a task blocked on M7's merge. Phase A cannot close: it ends in a checkpoint.

## Rules

`pyproject.toml` (ruff F, E9, B; pytest with warnings as errors and a 120 s timeout; mypy with `i18n` checked on
three platforms) and the roadmap's worker rules. No new runtime dependency: `gettext`, `ast`, `ctypes` and Qt's
own `QTranslator` are all already there.
