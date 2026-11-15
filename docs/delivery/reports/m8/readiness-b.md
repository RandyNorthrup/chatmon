# M8 readiness review, phase B

Requirements review of M8-01's phase B, on top of [phase A's](readiness.md). Reviewed on `wave3/m8` after merging
`improve/assessment-fixes` at `dd2e375` (M7 merged) and then `fd0fe70` (the coordinator's Qt 6.4 guards), Windows 11,
Python 3.14.10. Inputs: the coordinator's phase-B brief, M7's plan ([m7-integration.md](../../m7-integration.md):
its Integration notes for M8 and the sentences it built from pieces), and phase A's fix-up table
([m8-translation.md](../../m8-translation.md)).

## Scope

- The eight M7-owned files: `app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`, `asking.py`,
  `commands.py`, `settings.py`.
- Every fix-up in phase A's table, with its other end in `winfiles.py`, `richtext.py` or `updates.py`.
- M7's pieces: `_hello`'s agents and updates, "Ask {brain}", "Snooze {length}", `reminder_line`, the chats menu's
  "{title} · {when} (this one)", the tray tooltip, and `_key_status`'s sentences.
- Not redone: M7 already wired the language setting (`settings.DEFAULTS["language"]`, `i18n.setup` in the app and
  the CLI, Settings' language list).

The coordinator's boundary for phase B is those eight files, the template, the fix-ups' other ends and tests,
because M6B is changing every other file at the same time. M7 also added `chatswin.py` (the Chats window), with
sixteen user-facing strings. It's outside that boundary, so it gets its own criterion (`M8-01.A10`) and task
(`T5-chatswin`), blocked until M6B merges or the coordinator says otherwise. The plan can't close until it's done;
it ends in a checkpoint again.

## Decisions

| # | Question | Decision |
|---|---|---|
| D14 | The quick actions' words ("Explain this:"…) | They're typed into the ask box for the person to send or change: their own question, in their language. So they're translated. The brain's system prompt and the attachment framing still aren't. |
| D15 | config.toml's commented template | Stays English, like the keys: a file written once, for people to edit, and read back by code. The problems Chatmon reports about it are translated. |
| D16 | "You:" and "Attached:" in the transcript | One pair of strings: `richtext.you_label()`, `attached_label()` and `question_markdown()` write them, `render` finds turns by them, and `asking` and `app` both write through `question_markdown`. Translated, turns are still found. |
| D17 | updates' messages that the app read for meaning | `Updater.metered` and `Updater.failure` (`CHECK_FAILED`, `INSTALL_FAILED`, `NOT_READY`) carry the meaning; the words are only shown. |
| D18 | A repeat rule as a label | Its first letter is made a capital and the rest left as written. `str.capitalize()` lowered the rest: "9:00 am", and it would lower a German noun. The English changes to "Every day at 9:00 AM", in the app's bubble and the menu alike. |
| D19 | Bubble style names inside sentences | `menus.style_word(name)`: a word of its own per style, not the label cut at " (". `styles.py` is M6B's to touch now, so the table is in `menus.py`. |

## Failure behaviour and coverage

Nothing new: a missing translation shows English, as in phase A. `M8-01.A9` is proved by a whole Companion with a
German catalog (`tests/test_i18n_app.py`), the phase-B files' own tests, the whole suite and fourteen red drills.
`M8-01.A10` has its task, blocked.
