# M6B's archived receipts

These are the oldest receipts of [m6b-static-analysis-logging.md](../../../m6b-static-analysis-logging.md), moved out
of its ledger for the validator's plan limit: 108 in wave 4's final round, and 55 more in the plans round for v0.10.0
(both 2026-11-15). Each is exactly as it stood in the ledger: the same bytes, with the ledger's own indentation, in a
JSON array per round.

| File | Receipts | SHA-256 |
|---|---|---|
| [w4b-round-two.json](w4b-round-two.json) | 55, the `W4B-` receipts of wave 4's round two (bf9d8ac); moved in the plans round for v0.10.0 | `2060e27a928105bd80ed090ebb022e00221e719c160080bc1f131499a4850475` |
| [w4-round-one.json](w4-round-one.json) | 55, the `W4-` receipts of wave 4's first round (fb19cb9); moved in the final round | `df8b42139085f4c6d88018f46fc69ac0fe12a830938ff3101d7807aab74872b9` |
| [e-original.json](e-original.json) | 53, the `E-` receipts of M6B's own delivery, before wave 4; moved in the final round | `dcdf5b49f42c635c56827de24ed172006671ca3d97bd6de417c90d4b0e7020f3` |

**Where they were last.**

- `w4b-round-two.json`: in the plan at commit `d08f4d5` ("M6B closed on 45a17b3 after M6A's section, ..."),
  unchanged up to `7816159`. The plan's git blob there is `652f0fd02a2f6e151fcd1a58d0722c958e06be2b`.
- The final round's two files: at commit `6f2a708` ("M6B closed on 45a17b3: ..."), unchanged up to `86ec920`. The
  plan's git blob there is `85a5ec9a513e36fb5d6bae1551256f7484e2706b`.

`git show <blob>` prints the whole plan with them in it, and each receipt's text in these files occurs verbatim in
it.

**Why they moved.** The validator reads a plan of at most 4 MiB (`MAX_PLAN_BYTES` in its `delivery/reader.py`).

- **The final round.** The plan was 4,174,944 bytes, and binding the final round's receipts after M6A's section would
  have taken it past the limit. Taking those 108 out brought it to 2,582,244 bytes.
- **The plans round for v0.10.0.** The plan was 3,427,178 bytes. Binding that round's 56 receipts (about 13 KB each)
  would have taken it to within a few kilobytes of the limit. Taking round two's 55 out brought it to 2,595,023 bytes
  ([../../wave5/archive_receipts.py](../../wave5/archive_receipts.py), which checks each receipt is stale and its
  text verbatim in the plan, then replaces the plan through update-delivery.py).

Each time nothing else in the ledger changed: no other receipt, requirement, criterion or checkpoint. The tasks'
evidence lists lost these ids and nothing else. The narrative points here from each round's section.

**What they were.** History only. Every one had status `stale` when it moved: later rounds' receipts re-ran every
check they recorded. None was the current evidence for any obligation.
