## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 16 Windows drills and 1 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its lint, types, distro, coverage and test legs, with Packages run 43701523037 (the build jobs) ([reports/m6a/ci/observed-bf9d8ac.txt](reports/m6a/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m6a/wave4b/readiness.md)).

**M6A-10.A1 passes again** ([wave4b/docs-review.md](reports/m6a/wave4b/docs-review.md)). CONTRIBUTING.md's two
sentences are rewritten. Its new claim, that mypy passes with PyQt6 6.12.1's stubs, was checked on linux, win32 and
darwin in WSL. The rest of round two's runs:

- the 10 gate drills, on CI's own combined coverage data and against `fail_under = 84`;
- the distro drill, under podman;
- the reproducible wheel;
- the Windows Update opt-in;
- Dependabot's schema, with its new PyQt6 6.12.0 ignore.

**What remains: two pending operations, with their owners, not passing.**

- **P-RELEASE.** No v0.10.0 tag exists yet. Owner: Randy or the coordinator, at the release.
- **P-DEPENDABOT.** `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after the merge.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them.
