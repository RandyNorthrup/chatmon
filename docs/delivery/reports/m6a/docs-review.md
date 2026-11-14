# M6A-10: the contributor files, reviewed

A manual review of `SECURITY.md`, `CONTRIBUTING.md` and `.github/ISSUE_TEMPLATE/config.yml`: each claim checked against
the code, the workflows, `pyproject.toml` and the repository's settings. Done on the M6A tree, 2026-11-14.

## The repository accepts private reports

```
$ gh api repos/RandyNorthrup/chatmon/private-vulnerability-reporting
{"enabled":true}
```

So the issue chooser's new contact link, "Report a security problem", and SECURITY.md's link both lead to a form an
outsider can use (`/security/advisories/new`). The README's existing "Found a security problem?" link is the same.

## SECURITY.md

| Claim | Checked against |
|---|---|
| Report privately as an advisory; it stays private until a fixed release | GitHub's private vulnerability reporting, enabled (above) |
| The latest release gets fixes; 0.6.0 and later update themselves | `packaging/build.py notes()` says the same to every release's readers |
| What counts: the README's privacy promises, the installers, updater and release workflow | README "Privacy and security"; `.github/workflows/packages.yml` |
| `SHA256SUMS.txt`, signed Ed25519 with the release key, and the updater installs nothing else | `packages.yml`'s `checksums` job; `chatmon/releasecheck.py`; README's update bullet |
| The Windows installer is Authenticode-signed by Randy Northrup | `packages.yml`'s `sign-windows` and `test-signed-windows` jobs |
| From 0.10.0, a build provenance attestation per file; `gh attestation verify FILE --repo RandyNorthrup/chatmon` | `packages.yml`'s new `attest` job (actions/attest-build-provenance v4.2.2, `subject-path: dist/*`); 0.10.0 is the first release made by it (roadmap: the version becomes 0.10.0) |

No response time is promised: that's the owner's to set, if ever.

## CONTRIBUTING.md

| Claim | Checked against |
|---|---|
| Python 3.11 or newer | `requires-python = ">=3.11"` |
| `pip install --require-hashes -r packaging/requirements-dev.txt` is what CI installs | `ci.yml`'s `lint` and `types` jobs install exactly that |
| `pip install -e ".[dev]"` gives the same versions | `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` |
| `python -m chatmon` and `bin/chatmon` run the checkout | `chatmon/__main__.py`, `bin/chatmon` |
| Linux's libraries, `dbus` and `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6`; tests skip without them | `ci.yml`'s apt step and its `xvfb-run -a`; the skips' reasons in [linux-xvfb-run.log](linux-xvfb-run.log) and the distro logs |
| `CHATMON_INSTANCE=<name>` runs a separate Chatmon | M1A's integration note 7; `paths.instance()` |
| Offscreen, an address of the run's own | `tests/conftest.py` |
| Warnings are errors but `ResourceWarning`, a two-minute limit, skip reasons, pytest-timeout required | `[tool.pytest.ini_options]` |
| The three opt-in variables | `tests/test_windows.py` (`CHATMON_TEST_CLIPBOARD`, `CHATMON_TEST_WINDOWS_UPDATE`), `tests/test_presence.py` and `tests/gnome-session.sh` (`CHATMON_GNOME_SESSION`) |
| Coverage commands; CI combines and holds `fail_under` | `[tool.coverage.*]`; `ci.yml`'s `coverage` job |
| The distro command | `.github/scripts/distro-tests.sh`'s own usage line; `ci.yml`'s `distro` job |
| Red drills | `tests/drills/run.py`'s docstring |
| `ruff`, `mypy --platform`, `actionlint`, `zizmor --no-online-audits .github` | `ci.yml`'s `lint` and `types` jobs run the same commands |
| No new runtime dependencies; plain English; privacy promises; real Qt objects | ROADMAP owner decisions and rules for every worker |
| Locking: `.in` names versions, `.txt` locks with hashes, the command at the top of each `.txt` | the `--custom-compile-command` header uv wrote into each lock |
| `--exclude-newer` for two-week-old releases; Dependabot's weekly two-week-old updates | how the locks were made (the plan's Design); `.github/dependabot.yml` |
| Releasing: changelog, version, then push a `v<version>` tag | `packages.yml`: `on: push: tags: ["v*"]`, the tag-vs-version check, and the draft-then-publish job |

## The issue chooser

`.github/ISSUE_TEMPLATE/config.yml` keeps blank issues and the README link, and adds "Report a security problem"
first, pointing to `/security/advisories/new`.

Result: accurate as written.
