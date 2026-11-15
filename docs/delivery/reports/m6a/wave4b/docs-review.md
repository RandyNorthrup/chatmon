# M6A-10.A1, round two: the contributor files at bf9d8ac (2026-11-15)

Round one's re-review ([../wave4/docs-review.md](../wave4/docs-review.md), at fb19cb9) failed on two CONTRIBUTING.md
sentences that M6B had made untrue. This review reads `SECURITY.md`, `CONTRIBUTING.md` and
`.github/ISSUE_TEMPLATE/config.yml` again, claim by claim, against bf9d8ac and the repository's settings as observed
on 2026-11-15 ([../../wave4b/github-settings.txt](../../wave4b/github-settings.txt)).

## The repository's settings

Private vulnerability reporting is on (`{"enabled":true}`). Secret scanning, push protection and Dependabot's alerts and
security updates are on. `main` requires 19 checks, now including `sway`.

## SECURITY.md: holds (unchanged since round one)

- Private advisories at `/security/advisories/new`: reporting is on.
- The latest release gets fixes, and 0.6.0 and later update themselves.
- What counts: the README's privacy promises, the installers, the updater, `packages.yml`.
- `SHA256SUMS.txt` is signed with the release key, and the Windows installer is Authenticode-signed. The `checksums`,
  `sign-windows` and `test-signed-windows` jobs are unchanged.
- From 0.10.0, a build provenance attestation per file. The `attest` job is unchanged, and the first tagged release is
  still to come (P-RELEASE).

## The issue chooser: holds

"Report a security problem" still leads to `/security/advisories/new`.

## CONTRIBUTING.md: holds

| Claim | At bf9d8ac |
|---|---|
| **Was stale:** "`pyproject.toml` turns every warning into an error (`ResourceWarning` too ...)" (lines 35-36) | true: `filterwarnings = ["error"]` |
| **Was stale:** "mypy checks every module, with nothing exempted, on each platform" | true: `[tool.mypy]` has no overrides, and CI run 43701523023's three `types` jobs say "Success: no issues found in 70 source files" |
| **New:** "It also passes with the next PyQt6's stubs (6.12.1)" | true: mypy 2.4.1 with PyQt6 6.12.1 (`/var/tmp/m4a-venv` in WSL) said "Success: no issues found in 70 source files" for `--platform linux`, `win32` and `darwin` on bf9d8ac's files, the wayland work's modules included ([mypy-pyqt6-6.12.1-linux.log](mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`) |
| **New:** the three workarounds for 6.12.1's stubs: `chatmon/qtsignal.py`'s `pyqtSignal`, typed static constructors, `# type: ignore[arg-type]` with a reason | true: `chatmon/qtsignal.py` exists and says why, and the patterns are what the followups worker's diff added (`chatmon/updates.py`, `brains.py` among them) |
| **New:** the Windows and macOS builds carry Qt's translation for each language with a `.po`, and the Linux packages need Qt's translations package added to `recommends` with the first language | true: `packaging/build.py` picks them (the followups worker's `7972401`). The `recommends` line is an instruction for later, and nothing ships yet. |
| Set up with `pip install --require-hashes -r packaging/requirements-dev.txt`, which is what CI installs | true: `ci.yml`'s lint and types jobs |
| `pip install -e ".[dev]"` gives the same versions | true: `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed in round two's Windows suite |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | true: the test job's apt list (the `sway` job has its own list) |
| The two-minute limit, the skip reasons, the three opt-in variables | true |
| Coverage combined, failing below `fail_under` | true: `fail_under = 84` against CI's 86.5% |
| The distro command, red drills, `ruff`, `mypy --platform`, `actionlint`, `zizmor` | true, as in round one |
| Locking, releasing | true, as in round one: the example names the files from the repository root |

Result: pass. Evidence for bf9d8ac only. Another worker (wave4/crash) may change code for an intermittent Qt crash.
