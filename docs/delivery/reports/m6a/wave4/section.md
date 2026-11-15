## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the workflows' first runs, which this plan's checkpoint was waiting for, and re-ran every check whose receipt
had gone stale. The evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as
git stores them (ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time. The wayland
worker is changing `ci.yml`. The followups worker is changing packaging, the requirements and the mypy settings in
`pyproject.toml`. Their merges will make many of these receipts stale again.

**What the runs answered.** CI run 43677128712 on fb19cb9, Packages run 43675230966 on d3f6a6e (the same `.github/`,
`packaging/` and `pyproject.toml`), and PR #18's own checks. The PR's test merge has fb19cb9's tree, and its 23 checks
passed, with the 5 release jobs skipped. That includes Packages run 43677664360 on exactly these files. Their logs and job lists are in
[reports/wave4/ci/](reports/wave4/ci/), and the review is [wave4/ci-review.md](reports/m6a/wave4/ci-review.md).

- **P-CI-FIRST: resolved.** All 18 jobs succeeded: lint, types ×3, test ×9, distro ×3, gnome and coverage. They are the
  same 18 checks `main` now requires.
- **P-COVERAGE-FLOOR: answered.** Windows, macOS and Arm Linux combined measure 86.2% against `fail_under = 72`. The same
  data, combined here, gives the same total. The plan's next action, raising the floor to about 84, is a change to
  `pyproject.toml`, which the followups worker now owns. It is left to them, and the Outcome in ROADMAP.md lists it.
- **P-PACKAGES-PR: resolved.** The python, windows, macos (macos-latest and macos-15-intel) and linux jobs succeeded:
  locked installs, `SOURCE_DATE_EPOCH`, twine and the dist tests, `test-install-update.sh` in three containers, and
  M1A's macOS checks.
- **P-MYPY-MERGES: resolved.** M6B removed the exemption list, and mypy passes on linux, win32 and darwin (CI's types
  jobs).
- **P-RELEASE: still open.** No tag has been pushed. The Packages run skipped the five release jobs, as designed.
- **P-DEPENDABOT: still open.** Dependabot reads `.github/dependabot.yml` from `main`, which doesn't have it yet. The
  owner's 2026-11-14 settings turned on Dependabot alerts and security updates, which are separate from these version
  updates.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). The 6 pytest drills and the 10 gate drills (zizmor, actionlint, mypy, strict marks, pip's hashes,
the checksums step, the coverage floor on CI's own combined data, and the wheel job's three), every one green, red and
green again. The distribution drill: `distro-tests.sh` in debian:trixie under podman, green, then red with a failing
test, then green again. Also the reproducible-wheel check (`SOURCE_DATE_EPOCH`), the Windows Update opt-in both ways,
and Dependabot's schema. The requirements were reviewed again ([wave4/readiness.md](reports/m6a/wave4/readiness.md)).

**What remains.**

- **M6A-10.A1 fails its re-review.** CONTRIBUTING.md still says warnings are errors "all but ResourceWarning" and that
  mypy exempts modules with `ignore_errors`. M6B ended both. See [wave4/docs-review.md](reports/m6a/wave4/docs-review.md).
  T7 stays implemented until someone outside `docs/delivery/` rewrites those two sentences (the coordinator, or the
  followups worker).
- **P-RELEASE.** Randy or the coordinator, at the 0.10.0 tag.
- **P-DEPENDABOT.** The coordinator, after the PR reaches `main`.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.
