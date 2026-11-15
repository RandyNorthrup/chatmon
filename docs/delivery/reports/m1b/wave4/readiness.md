# M1B readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md), with its addendum. Its receipts went stale because the rules they
were bound to changed. This review re-reads M1B's obligations against the brief and rules as they are now. It is a
requirements review, not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M1B-01 to M1B-17. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The attached-text decision M1B-17 rests on is unchanged. No new
  decision touches brains or stored data.
- `pyproject.toml` at fb19cb9: M6A's stricter pytest settings and M6B's ruff and mypy settings, added since. The
  keychain and port-owner tests now run under every warning as an error and a 120 s limit. No criterion depends on a
  laxer setting.

## Requirements and criteria

All 17 requirements map one to one to AC-M1B-01 to AC-M1B-17. Each has an owning task, and its given/when/then is
still observable. No terminology conflicts.

## Since the last review

- **M7-WIRING.** M7 wired the APIs. Streaming is M7-01. Failures that say what to do are M7-02. Keys and the brain test
  in Settings are M7-03. A brain per chat, asking another brain, and backup in Settings are M7-09. The guard for
  brains that read files, settings problems and damaged files are INT-M1B. All of these are verified criteria in
  [m7-integration.md](../../../m7-integration.md), re-bound in this wave.
- **M1B-05 and M1B-12 moved.** The stale-folder tidy now runs on a thread of its own when the first `Asker` is made
  (`brains.py`, the `_tidying` thread). The HTTP stream's pieces are emitted in `_reply_read`. Their old drills'
  texts are gone, so wave 4's drills mutate the lines that do the work now. Both lines are still in T-M1B-A's and
  T-M1B-G's own file, `brains.py`.
- **Platforms.** The three CI pending operations named exact tests. CI run 43677128712 ran each of them, and none was
  skipped where it should run. The plan's reconciliation section gives the details.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
