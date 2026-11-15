# M6B's archived receipts

These are the 108 oldest receipts of [m6b-static-analysis-logging.md](../../../m6b-static-analysis-logging.md),
moved out of its ledger in wave 4's final round (2026-11-15). Each is exactly as it stood in the ledger: the same
bytes, with the ledger's own indentation, in a JSON array per round.

| File | Receipts | SHA-256 |
|---|---|---|
| [w4-round-one.json](w4-round-one.json) | 55, the `W4-` receipts of wave 4's first round (fb19cb9) | `df8b42139085f4c6d88018f46fc69ac0fe12a830938ff3101d7807aab74872b9` |
| [e-original.json](e-original.json) | 53, the `E-` receipts of M6B's own delivery, before wave 4 | `dcdf5b49f42c635c56827de24ed172006671ca3d97bd6de417c90d4b0e7020f3` |

**Where they were last.** In the plan at commit `6f2a708` ("M6B closed on 45a17b3: ..."), unchanged up to
`86ec920`. The plan's git blob there is `85a5ec9a513e36fb5d6bae1551256f7484e2706b`:
`git show 85a5ec9a513e36fb5d6bae1551256f7484e2706b` prints the whole plan with them in it, and each receipt's text
in these files occurs verbatim in it.

**Why they moved.** The validator reads a plan of at most 4 MiB (`MAX_PLAN_BYTES` in its `delivery/reader.py`). The plan
was 4,174,944 bytes, and binding the final round's receipts after M6A's section would have taken it past that. Taking
these out brought it to 2,582,244 bytes. Nothing else in the ledger changed: no other receipt, requirement, criterion
or checkpoint. The tasks' evidence lists lost these ids and nothing else. The narrative points here from the final
round's section.

**What they were.** History only. All 108 had status `stale` when they moved: later rounds' receipts (W4B-, W4C-,
W4E-, then W4F-) re-ran every check they recorded. None was the current evidence for any obligation.
