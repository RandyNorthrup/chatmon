# M6A-10.A1, the final round: the contributor files at 45a17b3 (2026-11-15)

Round three's review ([../wave4c/docs-review.md](../wave4c/docs-review.md), at 3586a0d) failed on one sentence.
CONTRIBUTING.md said mypy also passes with PyQt6 6.12.1's stubs, and the crash fix's `removeEventFilter(self)` made
that false. The quit guard (`86e84e0`) gave that line the `# type: ignore[arg-type]` with its reason. `SECURITY.md`,
`CONTRIBUTING.md`, `.github/`, `packaging/` and `pyproject.toml` are unchanged since 3586a0d (`git diff 3586a0d
45a17b3` lists none of them). This review reads the three files again, claim by claim, against 45a17b3 and the
repository's settings as observed on 2026-11-15 ([../../wave4e/github-settings.txt](../../wave4e/github-settings.txt)).

## The repository's settings

Private vulnerability reporting is on (`{"enabled":true}`). Secret scanning, push protection and Dependabot's alerts and
security updates are on. `main` requires the same 19 checks, `sway` among them.

## SECURITY.md: holds (unchanged)

- Private advisories at `/security/advisories/new`: reporting is on.
- The latest release gets fixes, and 0.6.0 and later update themselves.
- What counts: the README's privacy promises, the installers, the updater, `packages.yml`.
- `SHA256SUMS.txt` is signed with the release key, and the Windows installer is Authenticode-signed. The `checksums`,
  `sign-windows` and `test-signed-windows` jobs are unchanged.
- From 0.10.0, a build provenance attestation per file. The `attest` job is unchanged, and the first tagged release is
  still to come (P-RELEASE; the newest tag is v0.9.2).

## The issue chooser: holds

"Report a security problem" still leads to `/security/advisories/new`.

## CONTRIBUTING.md: holds

| Claim | At 45a17b3 |
|---|---|
| "`pyproject.toml` turns every warning into an error (`ResourceWarning` too ...)" | true: `filterwarnings = ["error"]`, unchanged |
| "mypy checks every module, with nothing exempted, on each platform" | true: `[tool.mypy]` has no overrides, and CI run 43743804662's three `types` jobs say "Success: no issues found in 70 source files" |
| "It also passes with the next PyQt6's stubs (6.12.1)" | **true again.** mypy 2.4.1 with PyQt6 6.12.1 says "Success: no issues found in 70 source files" for `--platform linux`, `win32` and `darwin` on 45a17b3's files. That holds in WSL (`/var/tmp/m4a-venv`: [mypy-pyqt6-6.12.1-linux.log](mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`) and here (M10's `mypy_runs.py` with `%TEMP%\m10-qt6121`: [../../m10/wave4f/mypy-6121.log](../../m10/wave4f/mypy-6121.log)). Round three's one error, `chatmon/app.py`'s `removeEventFilter(self)`, is gone. |
| The three workarounds for 6.12.1's stubs: `chatmon/qtsignal.py`'s `pyqtSignal`, typed static constructors, `# type: ignore[arg-type]` with a reason | true. The quit guard's line now follows the third, with its reason ("PyQt6 6.12.1's stub types the filter as the widget's own class (CONTRIBUTING.md)") |
| The Windows and macOS builds carry Qt's translation for each language with a `.po`, and the Linux packages need Qt's translations package added to `recommends` with the first language | true: `packaging/build.py` is unchanged; the `recommends` line is an instruction for later, and nothing ships yet |
| Set up with `pip install --require-hashes -r packaging/requirements-dev.txt`, which is what CI installs | true: `ci.yml`'s lint and types jobs |
| `pip install -e ".[dev]"` gives the same versions | true: `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed in this round's Windows suite ([../../wave4f/suite-windows.log](../../wave4f/suite-windows.log)) |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | true: the test job's apt list (the `sway` job has its own list) |
| The two-minute limit, the skip reasons, the three opt-in variables | true |
| Coverage combined, failing below `fail_under` | true: `fail_under = 84`; CI run 43743804662's coverage job held it (86.4%) |
| The distro command, red drills, `ruff`, `mypy --platform`, `actionlint`, `zizmor` | true, as in earlier rounds |
| Locking, releasing | true, as in earlier rounds: the example names the files from the repository root |

Result: pass.
