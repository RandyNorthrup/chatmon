# M8 readiness review, the Chats window

Addendum to [readiness.md](readiness.md) and [readiness-b.md](readiness-b.md), on `wave3/m8` after merging
`improve/assessment-fixes` at `210c6e0` (M6B's phase A). Windows 11, Python 3.14.10.

## Scope

`T5-chatswin` was blocked only by the file boundary: M6B was changing every file outside phase B's. M6B's phase A
didn't touch `chatmon/chatswin.py`, and the coordinator released it: this step touches `chatswin.py`, its tests, the
template and M8's plan and reports, nothing else (M6B's phase B is editing the eight hub files meanwhile).

## Decisions

| # | Question | Decision |
|---|---|---|
| D20 | The window's list lines | The same sentences as the menu's list of chats (`menus.chats_menu`): "{title}   ·   {when}", "{title}   ·   {when}  (this one)" and "A chat", so a translator translates them once and the two lists read alike. |
| D21 | The window's title | `TITLE` is a module constant, so it's `N_("Chats")`, shown as `_(TITLE)`. |

## Rechecks

M6B's merge changed files every earlier receipt is bound to (its lint and logging touched 95 files), so every check
runs again on the merged tree, with every drill's mutation text confirmed to still occur exactly once. The earlier
receipts stay in the ledger as history, marked stale. Ruff now has M6B's stricter rule sets, and mypy checks
`chatswin.py`.
