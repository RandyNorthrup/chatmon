# M6A-10.A1, round three: the contributor files at 3586a0d (2026-11-15)

Round two's review ([../wave4b/docs-review.md](../wave4b/docs-review.md), at bf9d8ac) passed. Its receipt went stale
because ROADMAP.md (a rule) is amended for round three. `SECURITY.md`, `CONTRIBUTING.md` and
`.github/ISSUE_TEMPLATE/config.yml` are unchanged since bf9d8ac (`git diff bf9d8ac 3586a0d` lists none of them). This
review reads them again, claim by claim, against 3586a0d and the repository's settings as observed on 2026-11-15
([../../wave4c/github-settings.txt](../../wave4c/github-settings.txt)).

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

| Claim | At 3586a0d |
|---|---|
| "`pyproject.toml` turns every warning into an error (`ResourceWarning` too ...)" | true: `filterwarnings = ["error"]`, unchanged |
| "mypy checks every module, with nothing exempted, on each platform" | true: `[tool.mypy]` has no overrides, and CI run 43729628408's three `types` jobs say "Success: no issues found in 70 source files" |
| "It also passes with the next PyQt6's stubs (6.12.1)" | **false at 3586a0d.** mypy 2.4.1 with PyQt6 6.12.1 finds one error on `--platform linux`, `win32` and `darwin`: `chatmon/app.py:3173: error: Argument 1 to "removeEventFilter" of "QObject" has incompatible type "Companion"; expected "AskBox"  [arg-type]`. That was seen in WSL (`/var/tmp/m4a-venv`: [mypy-pyqt6-6.12.1-linux.log](mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`) and here (M10's `mypy_runs.py` with `%TEMP%\m10-qt6121`: [../../m10/wave4c/mypy-6121.log](../../m10/wave4c/mypy-6121.log)). The line is the crash fix's new `widget.removeEventFilter(self)` in `Companion._stop_for_good`. At bf9d8ac the sentence was true. |
| The three workarounds for 6.12.1's stubs: `chatmon/qtsignal.py`'s `pyqtSignal`, typed static constructors, `# type: ignore[arg-type]` with a reason | true as advice, and unchanged. The crash fix's line is a case of the third (`removeEventFilter`'s filter typed as `Self`), and it doesn't carry the ignore. That is why the sentence above is false. |
| The Windows and macOS builds carry Qt's translation for each language with a `.po`, and the Linux packages need Qt's translations package added to `recommends` with the first language | true: `packaging/build.py` is unchanged; the `recommends` line is an instruction for later, and nothing ships yet |
| Set up with `pip install --require-hashes -r packaging/requirements-dev.txt`, which is what CI installs | true: `ci.yml`'s lint and types jobs |
| `pip install -e ".[dev]"` gives the same versions | true: `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed in round three's Windows suite |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | true: the test job's apt list (the `sway` job has its own list) |
| The two-minute limit, the skip reasons, the three opt-in variables | true |
| Coverage combined, failing below `fail_under` | true: `fail_under = 84` against CI's 86.4% at 3586a0d |
| The distro command, red drills, `ruff`, `mypy --platform`, `actionlint`, `zizmor` | true, as in rounds one and two |
| Locking, releasing | true, as in rounds one and two: the example names the files from the repository root |

Result: **fail**, on one sentence. CONTRIBUTING.md says mypy also passes with PyQt6 6.12.1's stubs, and at 3586a0d it
doesn't. CI can't see it, because its `types` jobs lock 6.11's stubs, which pass. The sentence is right about what
the code should be, so the fix is in the code, not the document: `# type: ignore[arg-type]` with the reason on
`chatmon/app.py:3173`, as CONTRIBUTING.md's third workaround says. That is product code, which this reconciliation
doesn't change. Owner: the coordinator. Then this review is done again. Everything else holds.
