# M6A-10.A1 again: the contributor files at fb19cb9 (wave 4, 2026-11-14)

The first review is [docs-review.md](../docs-review.md), done on the M6A tree. Its receipt went stale. This review reads
`SECURITY.md`, `CONTRIBUTING.md` and `.github/ISSUE_TEMPLATE/config.yml` claim by claim against fb19cb9's code,
workflows and `pyproject.toml`, and against the repository's settings as observed today.

## The repository's settings

```
$ gh api repos/RandyNorthrup/chatmon/private-vulnerability-reporting
{"enabled":true}
$ gh api repos/RandyNorthrup/chatmon --jq .security_and_analysis
dependabot_security_updates enabled, secret_scanning enabled, secret_scanning_push_protection enabled
```

The full answers are in [../../wave4/github-settings.txt](../../wave4/github-settings.txt).

## SECURITY.md: holds

| Claim | Checked against |
|---|---|
| Report privately as an advisory (`/security/advisories/new`) | private vulnerability reporting, enabled (above) |
| The latest release gets fixes; 0.6.0 and later update themselves | unchanged; `packaging/build.py notes()` |
| What counts: the README's privacy promises, the installers, the updater, `packages.yml` | README "Privacy and security"; `.github/workflows/packages.yml` |
| `SHA256SUMS.txt` signed with the release key (Ed25519); the updater installs nothing else | `packages.yml`'s `checksums` job; `chatmon/releasecheck.py` |
| The Windows installer is Authenticode-signed | `packages.yml`'s `sign-windows` and `test-signed-windows` jobs (skipped on a non-tag run, as designed: Packages run 43675230966) |
| From 0.10.0, a build provenance attestation per file, checked with `gh attestation verify` | `packages.yml`'s `attest` job. The first tagged release is still to come (M6A's P-RELEASE). |

## The issue chooser: holds

"Report a security problem" leads to `/security/advisories/new`, and the README link is unchanged.

## CONTRIBUTING.md: two claims are no longer true

| Claim | At fb19cb9 |
|---|---|
| Set up with `pip install --require-hashes -r packaging/requirements-dev.txt`, what CI installs | holds: ci.yml's `lint` and `types` jobs install exactly that (CI run 43677128712's lint log) |
| `pip install -e ".[dev]"` gives the same versions | holds: `tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs` passed (wave4 suite log) |
| Linux's libraries, `dbus`, `dbus-x11`, the Wayland protocol files, `xvfb-run` with `libxtst6` | holds: the same list as ci.yml's apt step |
| `CHATMON_INSTANCE`, the offscreen platform, a Chatmon address of the run's own | holds: `tests/conftest.py` |
| **"`pyproject.toml` turns warnings into errors (all but `ResourceWarning`, which is listed at the end instead)"** (lines 35-36) | **No longer true.** `filterwarnings = ["error"]` (pyproject.toml line 97): every warning is an error, ResourceWarning too, since M6B closed the last unclosed resources (M6B-RW). |
| Stops a test past two minutes (pytest-timeout, required); says why each skip skipped | holds: `timeout = 120`, `required_plugins`, `-rs` |
| The three opt-in variables | holds: `tests/test_windows.py` (612, 795), `tests/test_presence.py` (141), `tests/gnome-session.sh` |
| Coverage: CI combines every OS and fails below `fail_under` | holds: ci.yml's `coverage` job (86.2% against 72 in run 43677128712) |
| The distro command, and the red-drill harness | holds |
| `ruff`, `mypy --platform` for linux, win32 and darwin, `actionlint`, `zizmor --no-online-audits .github` | holds: ci.yml's `lint` and `types` jobs |
| **"mypy checks every module but those `pyproject.toml` exempts (`ignore_errors`). Taking a module off that list ... is always welcome."** | **No longer true.** `[tool.mypy]` has no overrides and no `ignore_errors`: M6B's phase B took the last modules off the list, and every module is checked (CI's three `types` jobs pass). |
| How the code is written; translations through `chatmon/i18n.py` | holds |
| Locking: `.in` files, hash-locked `.txt` files, the command at each `.txt` file's top | holds. The example names the files from the repository root and adds `--exclude-newer`; the files' own headers name them from `packaging/`. That is an example, not a contradiction. |
| Releasing: changelog, version, merge to main, push a `v<version>` tag; `packages.yml` drafts and publishes | holds: `on: push: tags: ["v*"]` and the draft-then-publish jobs |

## Result: fail

M6A-10.A1 says CONTRIBUTING.md "says how to set up, test, lint, lock and release as CI does", and two of its
sentences no longer do: the ResourceWarning exception and the mypy exemption list. The fix is two sentences in
`CONTRIBUTING.md`, which is outside `docs/delivery/` and so not this worker's to make. Next action: whoever next
edits `CONTRIBUTING.md` (the coordinator, or the followups worker, who owns the mypy settings) rewrites lines 35-36 to
say every warning is an error, and the mypy paragraph to say every module is checked. Then this review is repeated.
