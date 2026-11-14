# Gate notes

Failures in the full-suite gate runs that are not M2's, each checked against the untouched base commit.

| Gate | Test | Why it isn't M2's |
|---|---|---|
| gate-1 (subset run with the old `styles.py`) | `tests/test_app_smoke.py::test_a_hook_reaches_it` | Passed when run again on its own (`1 passed`). It talks to the companion through the per-user pipe `\.\pipe\chatmon-<user>`, which other worktrees' test runs on this machine open at the same time. |
| gate-2 | `tests/test_events.py::test_send_without_a_running_companion` | Fails the same way on the base commit `5346385` extracted with `git archive` into a scratch folder: something else on this machine (another worker's suite, or a running Chatmon) owns the per-user pipe, so `send` finds a companion. M2 changes nothing in `events.py`. |
| gate-4 | `tests/test_app_smoke.py::test_a_hook_reaches_it` | The per-user pipe again: re-run alone with `tests/test_events.py`, `19 passed, 9 skipped` (appended to gate-4.log). |
