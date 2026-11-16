# M6A-10.A1, the plans round for v0.10.0: the contributor files at 7816159 (2026-11-15)

The final round's review is [../wave4f/docs-review.md](../wave4f/docs-review.md) (at 45a17b3, pass). Since then
`CONTRIBUTING.md` changed in its Dependencies section only (PR #22, the Dependabot replacement); `SECURITY.md` and
`.github/ISSUE_TEMPLATE/config.yml` are unchanged (`git diff 45a17b3 7816159` lists neither). This review reads the
three files again, claim by claim, against 7816159, the first tagged release, and the repository's settings as
observed today ([../../wave5/github-settings.txt](../../wave5/github-settings.txt), [outcomes.log](outcomes.log)).

## The repository's settings

These are as in the final round:

- Private vulnerability reporting is on (`{"enabled":true}`).
- Secret scanning, push protection, and Dependabot's alerts and security updates are on.
- `main` requires the same 19 checks, `sway` among them.

## SECURITY.md: holds (unchanged), and its 0.10.0 promise is now observed

- Private advisories at `/security/advisories/new`: reporting is on.
- The latest release gets fixes; 0.6.0 and later update themselves.
- What counts: the README's privacy promises, the installers, the updater, `packages.yml`.
- `SHA256SUMS.txt` is signed with the release key (`SHA256SUMS.txt.sig`), and the Windows installer is
  Authenticode-signed. The v0.10.0 release has both:
  - every downloaded file matches `SHA256SUMS.txt`;
  - test-signed-windows found the installer "signed: Valid".
- "From 0.10.0 on, each file also has a build provenance attestation": true. `gh attestation verify <file> --repo
  RandyNorthrup/chatmon`, the command SECURITY.md gives, passed for each of v0.10.0's 11 files, the
  `chatmon_0.10.0-1_all.deb` it names among them ([outcomes.log](outcomes.log)).

## The issue chooser: holds

"Report a security problem" still leads to `/security/advisories/new`.

## CONTRIBUTING.md: one claim fails

| Claim | At 7816159 |
|---|---|
| Setting up: `pip install --require-hashes -r packaging/requirements-dev.txt` is what CI installs; `pip install -e ".[dev]"` gives the same versions | true: `ci.yml`'s lint and types jobs; `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed in this round's Windows suite ([../../wave5/suite-windows.log](../../wave5/suite-windows.log)) |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | true: the test job's apt list (the `sway` job has its own) |
| `pyproject.toml` turns every warning into an error (`ResourceWarning` too), the two-minute limit, each skip's reason | true: unchanged |
| The three opt-in variables (`CHATMON_TEST_CLIPBOARD`, `CHATMON_TEST_WINDOWS_UPDATE`, `CHATMON_GNOME_SESSION`) | true, and CI sets none of them. *Observation, not a failure:* PR #22 added a fourth opt-in test, `tests/test_pins.py::test_the_real_lists_with_the_real_uv` (`CHATMON_PINS_NETWORK=1`, uv against PyPI). The table doesn't list it, but its skip reason names the variable. The table opens "A few tests are left out unless asked for", and CI doesn't run that test either. |
| Coverage combined, failing below `fail_under`; the distro command; red drills | true: `fail_under = 84`; main's CI run 43778643147's coverage job held it (86.4%) |
| `ruff`, `mypy --platform` for each, `actionlint`, `zizmor --no-online-audits .github` | true: CI run 43778643147's lint and types jobs, all green |
| "mypy checks every module, with nothing exempted, on each platform" | true: `[tool.mypy]` checks `chatmon` with no overrides, and the three `types` jobs say "Success: no issues found in 70 source files" (`packaging/pins.py`, which isn't Chatmon, gets `mypy --strict` in pins.yml's own types job) |
| "It also passes with the next PyQt6's stubs (6.12.1)" | **false at 7816159.** mypy 2.4.1 with PyQt6 6.12.1 finds two errors, the same on `--platform linux`, `win32` and `darwin`, in WSL ([mypy-pyqt6-6.12.1-linux.log](mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`), here ([../../m10/wave5/mypy-6121.log](../../m10/wave5/mypy-6121.log)) and in the how-to's own replay ([../../m10/wave5/howto-replay.log](../../m10/wave5/howto-replay.log)): `chatmon/layer.py:824: error: Need type annotation for "app"  [var-annotated]` and `chatmon/layer.py:917:` the same. Both lines are `app = QGuiApplication.instance()`, new in PR #22's KWin and Hyprland fixes (6f7dd3f: `_watch_qt_focus` and `close`). 6.12.1's stubs type the static `instance()` as returning `Self`, the case CONTRIBUTING.md's second workaround covers ("a value from a static constructor ... is given its type"), and these two lines don't have it. CI is green because its types jobs lock 6.11's stubs. |
| The three workarounds for 6.12.1's stubs | true as instructions; the new code in `layer.py` needed the second and lacks it (above) |
| Words people see, and translations | true: unchanged; `packaging/extract_strings.py --check` passes ([../../wave5/extract-strings-check.log](../../wave5/extract-strings-check.log)) |
| **Dependencies** (new): lock again with the command at the top of the `.txt`, run in `packaging/` | true: each header's command, run in a copy of `packaging/`, gives the committed locks byte for byte ([../../m10/wave5/locks.log](../../m10/wave5/locks.log)) |
| Dependabot proposes newer actions every week, each once it's two weeks old, and can't lock these lists | true: `dependabot.yml` ([pins-review.md](pins-review.md)); its pip pull requests #19-#21 dropped the other platforms' packages |
| The pins workflow runs `pins.py` with uv from `requirements-pins.txt`, takes only releases two weeks old, and keeps one issue, "Python pins ready to move", while something can | true: pins.yml and its runs on `main` (#23, opened once and edited once) ([pins-review.md](pins-review.md)) |
| `pins.py --apply` moves the `.in` pins, the dev extra, and each lock with its own command | true: `tests/test_pins.py`'s apply tests and the drills PINS-dev-extra, PINS-seed, PINS-universal ([drills-pins.log](drills-pins.log)) |
| Dependabot's security updates still come for Python packages; relock such a pull request with uv; `pins.py` leaves a newer release where it is | true: security updates `enabled`; `test_nothing_moves_backwards` and PINS-backwards |
| Releasing: tag the merged commit `v<version>`; the packages workflow builds, installs, signs, drafts with the notes and every file, and publishes once all are attached | true, and now observed: v0.10.0, an annotated tag on 7816159, Packages run 43778675599 ([ci-review.md](ci-review.md)) |

Result: **fail**, on one sentence, as in round three. CONTRIBUTING.md's "It also passes with the next PyQt6's stubs
(6.12.1)" is false at 7816159, because of two lines of PR #22's KWin and Hyprland fixes. The sentence says what the
code should be, so the fix is in the code, which this round doesn't change. Next: the coordinator gives `app` its type
at `chatmon/layer.py:824` and `:917` (`app: QCoreApplication | None = QGuiApplication.instance()`, CONTRIBUTING.md's
second workaround). Then mypy with 6.12.1's stubs runs again, and this review is done again. Every other claim
holds. The opt-in table could also name `CHATMON_PINS_NETWORK`, a note for the coordinator.
