## Reconciliation, wave 4, final round (2026-11-15)

The final round re-bound this plan at **45a17b3**: `improve/assessment-fixes` with the quit guard (`86e84e0`), the
toast fix (`8c24b1c`), wave4/mac-drills and wave4/mac-owner merged. None of its receipts went stale on 45a17b3's files
([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). Round three's one failure, M6A-10.A1, was
first bound as passing without a section here (W4E-MAN-DOCS), so that nothing else would go stale. That left this
plan's text saying M6A-10.A1 fails while its ledger said it passes. This section puts them back in agreement. A plan's
prose is in every receipt's scope, so every check of the plan was run again on 45a17b3 or read from its CI runs.

**What was re-run.** The whole suite on Windows ([wave4f/suite-windows.log](reports/wave4f/suite-windows.log):
1259 passed, 179 skipped), then 16 Windows drills and one Linux drill (in WSL). Every one went green, red and green again: M6A's
own 6, the 10 gate drills (on CI's own combined coverage data for 45a17b3, 86.4% against `fail_under = 84`), and the
distro drill under podman. The reproducible wheel, the Windows Update opt-in and Dependabot's schema were checked
again. CI run 43743804662 (PR #18 at 45a17b3, all 19 jobs green, its test merge `eb8a996` with 45a17b3's own tree:
[reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)) was read for its lint, types, distro, coverage
and test legs, with Packages run 43743804716 (the build jobs)
([reports/m6a/ci/observed-45a17b3.txt](reports/m6a/ci/observed-45a17b3.txt)). The requirements and the workflows
were reviewed again ([wave4f/readiness.md](reports/m6a/wave4f/readiness.md),
[wave4f/ci-review.md](reports/m6a/wave4f/ci-review.md)).

**M6A-10.A1 passes again** ([wave4f/docs-review.md](reports/m6a/wave4f/docs-review.md)). The quit guard gave
`chatmon/app.py`'s `removeEventFilter(self)` the `# type: ignore[arg-type]` with its reason. So CONTRIBUTING.md's
"It also passes with the next PyQt6's stubs (6.12.1)" is true again. mypy 2.4.1 with 6.12.1's stubs finds no issues
on linux, win32 and darwin, in WSL ([wave4f/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4f/mypy-pyqt6-6.12.1-linux.log),
`-win32`, `-darwin`) and here ([reports/m10/wave4f/mypy-6121.log](reports/m10/wave4f/mypy-6121.log)). T7 is
verified.

**What remains: two pending operations, with their owners, not passing.** Both are as before
([reports/wave4e/github-settings.txt](reports/wave4e/github-settings.txt), observed again):

- **P-RELEASE.** No v0.10.0 tag exists yet; the newest is v0.9.2. Owner: Randy or the coordinator, at the release.
- **P-DEPENDABOT.** `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after the merge.

**Receipts.** Round three's W4C- receipts, and this round's first W4E-MAN-DOCS, are now stale history, with their
hashes untouched. The W4F- receipts replace them.
