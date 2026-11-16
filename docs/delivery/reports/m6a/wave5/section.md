## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). All 33 of its passing receipts went stale, on
`.github/dependabot.yml`, `CONTRIBUTING.md`, `tests/test_cli.py` and `tests/test_requirements.py`
([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)), and both pending operations had come due.
Each was observed before anything was recorded ([wave5/outcomes.log](reports/m6a/wave5/outcomes.log)).

**P-RELEASE: done.** `v0.10.0`, an annotated tag ("Chatmon 0.10.0") on 7816159, was pushed. Packages run
43778675599 ran every job and all ten succeeded:

- the builds: python, windows, both macos and linux;
- sign-windows and test-signed-windows: the installer and both executables "signed: Valid";
- checksums: `SHA256SUMS.txt`, signed;
- attest: "Attestation created for 11 subjects";
- publish: drafted the release with every file, checked that the draft held exactly those files, then published it.

v0.10.0 is published (2026-11-16T00:37:23Z), not a draft, with 11 files. Each file matches `SHA256SUMS.txt`, and
`gh attestation verify` passed for each: SLSA provenance from `packages.yml@refs/tags/v0.10.0`, source 7816159
([wave5/ci-review.md](reports/m6a/wave5/ci-review.md)). M6A-07.A1 holds on the real run.

**P-DEPENDABOT: done, and M6A-02 replaced.** Once `.github/dependabot.yml` reached `main` (65ed989), Dependabot's
first run opened #19, #20 and #21. Each locked our `uv pip compile --universal` lists again with pip-compile, for one
platform, and dropped the macOS build's packages and nuitka's Windows marker. The owner closed all three, each with a
comment. PR #22 replaced both pip entries with `packaging/pins.py`, run weekly by `.github/workflows/pins.yml`, and
`dependabot.yml` keeps only github-actions. Dispatched on `main`, Pins run 43778713259 opened #23 ("Python pins ready
to move": nuitka 4.3.1 → 4.3.4, PyQt6 6.12.0 held back), and run 43778794994 edited #23 in place; there is no second
issue ([wave5/pins-review.md](reports/m6a/wave5/pins-review.md)).

So M6A-02.A1 ("github-actions, pip in /packaging and pip in /") fails as written. Its re-review is recorded as
W5-MAN-DEPENDABOT, status fail, with the reason. The requirement changed by the owner's decision, so it is
superseded rather than rewritten (scope revision 2, [wave5/readiness.md](reports/m6a/wave5/readiness.md)):

- **M6A-02B** replaces M6A-02. Dependabot keeps github-actions up to date, and a weekly uv check proposes the Python
  pins' updates, each at least 14 days old.
  - A1: `dependabot.yml`, the actions only, and why.
  - A2: the pins check's rules, with the nine drills of [reports/m6a/pins/](reports/m6a/pins/README.md).
  - A3: pins.yml, its permissions, its one issue, its types job.
- **T7B** replaces T7. It keeps T7's files and M6A-10.A1, and adds the pins check's files.

**What was re-run.** The whole suite on Windows ([reports/wave5/suite-windows.log](reports/wave5/suite-windows.log):
1293 passed, 225 skipped). Then 25 Windows drills and the distro drill under podman in WSL:

- M6A's own 6;
- the pins check's 9;
- the 10 gate drills, on CI's own combined coverage data for 7816159: 86.4% against `fail_under = 84`
  ([wave5/coverage-combined.log](reports/m6a/wave5/coverage-combined.log)).

Every one went green, red and green again. The reproducible wheel, the Windows Update opt-in, the Dependabot and
workflow schemas and the pins check's own types job were checked again. main's CI run 43778643147 on 7816159 (all 19
jobs green; each checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read
for its lint, types, distro, coverage and test legs, with the tag's Packages run and the Pins runs
([reports/m6a/ci/observed-7816159.txt](reports/m6a/ci/observed-7816159.txt)). The workflows and the contributor files
were reviewed again ([wave5/ci-review.md](reports/m6a/wave5/ci-review.md),
[wave5/docs-review.md](reports/m6a/wave5/docs-review.md)). One note for the coordinator, not a failure: CONTRIBUTING.md's
opt-in table doesn't name `CHATMON_PINS_NETWORK`.

**M6A-10.A1 fails again, on the same sentence as in round three.** CONTRIBUTING.md says mypy "also passes with the
next PyQt6's stubs (6.12.1)". At 7816159 mypy 2.4.1 with 6.12.1's stubs finds two errors on linux, win32 and darwin:
`chatmon/layer.py:824: error: Need type annotation for "app"  [var-annotated]`, and `:917` the same. It does so in
WSL ([wave5/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5/mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`) and
here ([reports/m10/wave5/mypy-6121.log](reports/m10/wave5/mypy-6121.log)).

Both lines are `app = QGuiApplication.instance()` in PR #22's KWin and Hyprland fixes (6f7dd3f). 6.12.1's stubs type
the static `instance()` as returning `Self`, which CONTRIBUTING.md's second workaround covers, and the two lines don't
have it. CI is green because its types jobs lock 6.11's stubs; the release's own gates ran mypy with 6.11's only. The
fix is in the code, which this round doesn't change. W5-MAN-DOCS is recorded as failing, and T7B is blocked on it.
Next: the coordinator gives `app` its type on both lines
(`app: QCoreApplication | None = QGuiApplication.instance()`). Then mypy with 6.12.1's stubs and the docs review run
again, and T7B can be verified.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace them. T7's
receipts stay with T7, superseded. Nothing is pending. M6A stops on M6A-10.A1 at 7816159; every other criterion
passes.
