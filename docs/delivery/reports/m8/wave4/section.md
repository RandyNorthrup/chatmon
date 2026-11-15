## Reconciliation, wave 4 (2026-11-14)

This plan closed with its CI legs still to come, and every receipt went stale afterwards. M6B's phase B and the M0,
M5 and M7 plans it takes as inputs changed, and the hashes had been taken on a CRLF checkout while git stores LF. Wave 4
re-ran the checks on **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes (ROADMAP.md,
*Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and `ci.yml`; followups:
packaging, the requirements and the mypy settings). Their merges will make some of these receipts stale again, and any
string they add must be in the template.

**What CI answered.** CI run 43677128712 on fb19cb9 had every job green. It ran `tests/test_i18n.py`,
`tests/test_i18n_app.py` and `tests/test_chatswin.py` on the Linux and macOS legs the closing next action named, and they
passed ([reports/m8/ci/observed.txt](reports/m8/ci/observed.txt)). Two of them skip in some places, by design and with
their reasons: Qt's own translations test, in the distribution containers that don't install them; and the
preferred-languages test, on macOS, where Qt reads the system's list.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). `packaging/extract_strings.py --check`
([wave4/extract-strings-check.log](reports/wave4/extract-strings-check.log)). Then all 43 drills of the plan's four drill
specs, every one green, red and green again. The requirements were reviewed again against the amended rules and the
re-bound M0, M5 and M7 plans ([wave4/readiness.md](reports/m8/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M8 on fb19cb9.
