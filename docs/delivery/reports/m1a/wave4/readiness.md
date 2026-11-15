# M1A readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier reviews are in [readiness.md](../readiness.md): the first at `5346385`, and the addendum after
implementation. Their receipts went stale because the rules they were bound to changed. This review re-reads M1A's
obligations against the brief and rules as they are now. It is a requirements review, not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M1A-01 to M1A-12 and M6A-14. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. One decision touches M1A's ground: the repository's security
  settings are now on (secret scanning, push protection, Dependabot alerts and security updates, main protected by the
  18 CI checks). It adds no obligation to M1A's requirements and conflicts with none.
- `pyproject.toml` at fb19cb9: M6A's stricter pytest settings and M6B's ruff and mypy settings, added since. No M1A
  criterion depends on a laxer setting.

## Requirements and criteria

All 13 requirements still map both ways to their 17 criteria. AC-10 is still manual, and its reason still applies: it is
a documentation-only change whose behavior is covered by tests. Every criterion still has an owning task. The platform
reach is unchanged: AC-01-LINUX and AC-01-MACOS name their platforms, and the other criteria run on Windows or
everywhere.

## Since the last review

- The three pending operations now have outcomes:
  - **Conftest isolation (MERGE-ISOLATION).** It landed: `tests/conftest.py` gives each test its own `LOCALAPPDATA` and
    sets `CHATMON_INSTANCE`, and the whole suite passes on Windows.
  - **Containers (CI-CONTAINER).** `packages.yml`'s Linux job runs `packaging/linux/test-install-update.sh` in the
    ubuntu, debian and fedora containers, without a caller's checksum.
  - **macOS (CI-MACOS).** CI ran the macOS tests.
- The `client_is_me` call that M1A offered (Integration notes 3) is now made by `app.py`'s accept path (M7). AC-10's
  wording, "described as a check offered to the accept path", still holds. The review in
  [review-ac10.md](review-ac10.md) says how.

## Findings

- AC-01-MACOS asks for a red drill. One exists in outline (drop the ownership test from `_MACOS_ROOT`'s `find`), but
  its test needs macOS: `ditto`, BSD `find` and `osascript`. No Mac is available here or in the test lab, and the drill
  can't be run in CI without pushing a branch. The criterion is clear and testable. Only the place to run its drill is
  missing.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
