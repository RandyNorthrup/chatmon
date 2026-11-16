# M6A-10.A1, the plans round for v0.10.0, bound again at 56caddd: the contributor files (2026-11-15)

This round's first review is [../wave5/docs-review.md](../wave5/docs-review.md), at 7816159. It failed on one
sentence, CONTRIBUTING.md's "It also passes with the next PyQt6's stubs (6.12.1)", because two lines of PR #22's
`chatmon/layer.py` lacked the second workaround. The coordinator's df3e93c gives them their type and adds
`CHATMON_PINS_NETWORK=1` to CONTRIBUTING.md's opt-in table; 56caddd changes a test only. `SECURITY.md` and
`.github/ISSUE_TEMPLATE/config.yml` are unchanged. This review reads the three files again, claim by claim, against
56caddd. The repository's settings and the release are as observed in the first review
([../../wave5/github-settings.txt](../../wave5/github-settings.txt), [../wave5/outcomes.log](../wave5/outcomes.log)).

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

## CONTRIBUTING.md: holds

| Claim | At 56caddd |
|---|---|
| Setting up: `pip install --require-hashes -r packaging/requirements-dev.txt` is what CI installs; `pip install -e ".[dev]"` gives the same versions | true: `ci.yml`'s lint and types jobs; `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed in this round's Windows suite ([../../wave5b/suite-windows.log](../../wave5b/suite-windows.log)) |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | true: the test job's apt list (the `sway` job has its own) |
| `pyproject.toml` turns every warning into an error (`ResourceWarning` too), the two-minute limit, each skip's reason | true: unchanged |
| The opt-in variables: `CHATMON_TEST_CLIPBOARD`, `CHATMON_TEST_WINDOWS_UPDATE`, `CHATMON_GNOME_SESSION` and, since df3e93c, `CHATMON_PINS_NETWORK` | true, and CI sets none of them. The fourth is `tests/test_pins.py::test_the_real_lists_with_the_real_uv` (uv against PyPI), whose skip reason names it; the row says what it runs ("`packaging/pins.py` with the real uv against PyPI, as the weekly Pins workflow runs it") |
| Coverage combined, failing below `fail_under`; the distro command; red drills | true: `fail_under = 84`; PR #24's CI run 43794815103's coverage job held it at 56caddd (86.4%), and CI's own data combined here gives the same total ([coverage-combined.log](coverage-combined.log)) |
| `ruff`, `mypy --platform` for each, `actionlint`, `zizmor --no-online-audits .github` | true: CI run 43794815103's lint and types jobs, all green |
| "mypy checks every module, with nothing exempted, on each platform" | true: `[tool.mypy]` checks `chatmon` with no overrides, and the three `types` jobs say "Success: no issues found in 70 source files" (`packaging/pins.py`, which isn't Chatmon, gets `mypy --strict` in pins.yml's own types job) |
| "It also passes with the next PyQt6's stubs (6.12.1)" | **true again.** mypy 2.4.1 with PyQt6 6.12.1 says "Success: no issues found in 70 source files" for `--platform linux`, `win32` and `darwin` on 56caddd, in WSL ([mypy-pyqt6-6.12.1-linux.log](mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`), here ([../../m10/wave5b/mypy-6121.log](../../m10/wave5b/mypy-6121.log)) and in the how-to's own replay ([../../m10/wave5b/howto-replay.log](../../m10/wave5b/howto-replay.log)). df3e93c typed `layer.py:824` and `:917` as the second workaround says. |
| The three workarounds for 6.12.1's stubs | true, and since df3e93c the new code in `layer.py` follows the second |
| Words people see, and translations | true: unchanged; `packaging/extract_strings.py --check` passes ([../../wave5b/extract-strings-check.log](../../wave5b/extract-strings-check.log)) |
| **Dependencies** (new): lock again with the command at the top of the `.txt`, run in `packaging/` | true: each header's command, run in a copy of `packaging/`, gives the committed locks byte for byte ([../../m10/wave5b/locks.log](../../m10/wave5b/locks.log)) |
| Dependabot proposes newer actions every week, each once it's two weeks old, and can't lock these lists | true: `dependabot.yml` ([pins-review.md](pins-review.md)); its pip pull requests #19-#21 dropped the other platforms' packages |
| The pins workflow runs `pins.py` with uv from `requirements-pins.txt`, takes only releases two weeks old, and keeps one issue, "Python pins ready to move", while something can | true: pins.yml and its runs on `main` (#23, opened once and edited once) ([pins-review.md](pins-review.md)) |
| `pins.py --apply` moves the `.in` pins, the dev extra, and each lock with its own command | true: `tests/test_pins.py`'s apply tests and the drills PINS-dev-extra, PINS-seed, PINS-universal ([drills-pins.log](drills-pins.log)) |
| Dependabot's security updates still come for Python packages; relock such a pull request with uv; `pins.py` leaves a newer release where it is | true: security updates `enabled`; `test_nothing_moves_backwards` and PINS-backwards |
| Releasing: tag the merged commit `v<version>`; the packages workflow builds, installs, signs, drafts with the notes and every file, and publishes once all are attached | true, and now observed: v0.10.0, an annotated tag on 7816159, Packages run 43778675599 ([ci-review.md](ci-review.md)) |

Result: pass. Every claim holds at 56caddd.
