## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI run this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered.** CI-posix is resolved. In CI run 43677128712 on fb19cb9, with every job green, both POSIX-only tests
passed on all three Ubuntu legs, all three macOS legs and the ubuntu, debian and fedora containers
([reports/m0/ci/observed.txt](reports/m0/ci/observed.txt)): `test_chatmon_ask_from_a_terminal_reaches_it` (M0-12) and
the log test (M0-13). The log test is now `tests/test_log.py::test_the_log_is_readable_only_by_you_and_never_followed_through_a_link`,
because M6B moved the log into `chatmon/log.py`.

**What moved, and what the tasks say now.**

- **T-M0-13.** Its changes gain `chatmon/log.py` and `tests/test_log.py`, so its receipts bind the code that makes the log
  0600 today. Its red drills (the log left at the umask; the log followed through a link) ran in WSL.
- **T-M0-05.** Its changes gain `chatmon/offline.py`. M5's phrase data and `load_phrases` now carry the per-language
  tables that `commands.Table` reads, and the rule that English wins a shared phrase is there.
- **T-M0-03-light.** It is no longer blocked. M7 delivered `ChatBook.listing()`, and `menus.chats_menu` builds the Chats
  submenu from `c.chat_book.listing(RECENT_CHATS)`.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then the plan's 22 drills that still apply, every one green, red and green again. Ten drills
mutated text that M5, M7 and M8 rewrote ([wave4/drills-left-out.txt](reports/m0/wave4/drills-left-out.txt)), so
their criteria got new drills on the lines that carry them now, all green, red and green:

- W4-M0-01-priority (M0-01.A1)
- W4-M0-04-appearance (M0-04.A1, A2)
- W4-M0-04-reload-under-help (A3)
- W4-M0-05-hide-not-kept (M0-05.A1)
- W4-M0-05-language-table-ignored and W4-M0-05-english-loses (A2)
- W4-M0-09-password-read-out (M0-09.A1)
- W4-M0-12-come-forward (M0-12.A2)
- W4-M0-03-light-limit (M0-03.A3)
- the two log drills in WSL (M0-13.A1)

Two more drills survived, and are kept as failed red receipts:

- **W4-M0-05-unknown-id-kept.** The drill was wrong, not the test: `load_phrases` drops an unknown id before `Table`
  sees it. The two A2 drills above replace it.
- **W4-M0-03-light-copies.** This one is a real gap. The menu built from whole chats (`recent()`) instead of the
  listing still passes `test_the_menu_lists_the_newest_chats_and_all_chats_opens_the_window`.

The requirements were reviewed again against the amended rules ([wave4/readiness.md](reports/m0/wave4/readiness.md)).

**What remains.** M0-03.A3 says the Chats submenu is built "without copying the chats". The code does that today, but no
test would notice if it stopped. T-M0-03-light stays implemented until a worker who may change code adds a menu-level
test to `tests/test_app_smoke.py` that fails when `chats_menu` reads whole chats. Then W4-M0-03-light-copies is run again
and must go red. The coordinator decides who adds the test. Severity: low, a performance property.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.
