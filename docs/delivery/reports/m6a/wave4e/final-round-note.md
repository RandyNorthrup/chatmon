# M6A in wave 4's final round (2026-11-15)

This note is kept beside the plan, not in it. A plan's prose is part of every receipt's scope, so a new section in
m6a-ci-tooling.md would make every M6A receipt stale, though none of them went stale on 45a17b3's files. The final
round adds one receipt and changes one task's state, and this note says why. Links are from docs/delivery/.

None of this plan's receipts went stale at **45a17b3**
([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). The final round re-binds it for round
three's one failure, M6A-10.A1, and nothing else.

**M6A-10.A1 passes again** ([wave4e/docs-review.md](reports/m6a/wave4e/docs-review.md)). The quit guard (`86e84e0`)
gave `chatmon/app.py`'s `removeEventFilter(self)` the `# type: ignore[arg-type]` with its reason. So CONTRIBUTING.md's
"It also passes with the next PyQt6's stubs (6.12.1)" is true again. mypy 2.4.1 with 6.12.1's stubs finds no issues on
linux, win32 and darwin, in WSL ([wave4e/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4e/mypy-pyqt6-6.12.1-linux.log),
`-win32`, `-darwin`) and here ([reports/m10/wave4e/mypy-6121.log](reports/m10/wave4e/mypy-6121.log)). W4E-MAN-DOCS
replaces round three's failing W4C-MAN-DOCS, which stays as history, and T7 is verified.

**What remains: two pending operations, with their owners, not passing.** Both are as before
([reports/wave4e/github-settings.txt](reports/wave4e/github-settings.txt), observed again):

- **P-RELEASE.** No v0.10.0 tag exists yet; the newest is v0.9.2. Owner: Randy or the coordinator, at the release.
- **P-DEPENDABOT.** `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after the merge.

**Receipts.** Every other receipt is round three's and still validates at 45a17b3.
