# M0 readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The first review is [readiness-review.md](../readiness-review.md), done at `5346385`. Its receipt went stale because the
rules it was bound to changed. This review re-reads the plan's obligations against the brief and rules as they are now,
and against the code that carries each one today. It is a requirements review, not proof that the code works. The
behavior and red receipts are the proof.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M0-01 to M0-13. Unchanged since the first review.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4. Three things were added: the canonical-bytes rule (evidence
  binds the repository's LF bytes), the rule for evidence from elsewhere (CI logs and WSL runs recorded under the plan's
  Windows profile), and the owner decisions of 2026-11-14 plus the Outcome. None of them adds, removes or changes an M0
  obligation.
- `pyproject.toml` at fb19cb9. Since `5346385` it has gained M6A's pytest settings (strict marks, `-rs`, every warning
  an error, `pytest-timeout` required at 120 s per test), M6B's ruff families and mypy settings, and the package-data
  globs. These make the checks stricter. No M0 criterion depends on a laxer setting, and the whole suite passes under
  them (wave4 suite log).

## Requirements and criteria

Every requirement (M0-01 to M0-13, M0-CLI) still has acceptance coverage in both directions, an owning task, and
observable given/when/then. No requirement is superseded and no ID is reused. No terminology conflicts: the menu
labels the criteria name ("Appearance", "Help & updates", "Reload settings file") are still the English text, now
wrapped for translation by M8.

## What moved since, and what the plan does about it

- **M0-13 (the log made 0600).** M6B moved the log into `chatmon/log.py` (`_private`, `log.setup`), and the test is now
  `tests/test_log.py::test_the_log_is_readable_only_by_you_and_never_followed_through_a_link`. `app.py` only calls
  `log.setup()`. T-M0-13's changes gain `chatmon/log.py` and `tests/test_log.py`, so its receipts bind the code that
  does the work. The criterion itself is unchanged.
- **M0-05 (the phrase table).** M5 moved the phrases into `chatmon/phrases/en.json`, read by `offline.load_phrases`.
  That function now carries the per-language tables and the rule that English wins a shared phrase. `commands.Table`
  still decides which phrases run its commands: the `COMMANDS` table, the table it is given, and `find`. T-M0-05's
  changes gain `chatmon/offline.py`, so its receipts bind the code that carries M0-05.A2 today. The old drills mutated
  text that has gone.
- **M0-03.A3 (the light listing).** T-M0-03-light was blocked on `ChatBook.listing()`. M7 delivered it (`chats.py`
  line 271), and `menus.chats_menu` now builds the submenu from `c.chat_book.listing(RECENT_CHATS)` (line 272). The
  blocker is gone and the task can be verified against its own file, `menus.py`.

## Findings

- The menu-side half of M0-03.A3, "without copying the chats", is a property of `listing()`. That is checked by
  `tests/test_chatswin.py::test_the_listing_has_titles_times_and_pins_never_messages`. No test at the menu would notice
  `chats_menu` going back to whole chats. Wave 4's drill W4-M0-03-light-copies probes exactly that; its result is in
  the plan's reconciliation section. Severity: low, because it is a performance property.

Result: ready. The obligations are clear and consistent with the current brief and rules, and the task changes above
keep each receipt bound to the code that carries its criterion.
