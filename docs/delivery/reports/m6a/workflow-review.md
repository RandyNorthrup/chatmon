# M6A: the workflows, reviewed against the done-when

A manual review of `.github/workflows/ci.yml` and `.github/workflows/packages.yml` on the M6A tree, for the parts that
only GitHub can run: triggers, cancellation, time limits, runners, the release's order, and the checkouts. Line
numbers are the files' as committed with this review. The mechanical checks are in [workflow-lint.log](workflow-lint.log)
(actionlint 1.7.12 with shellcheck 0.11.0 on Linux, and zizmor 1.31.1); the gate drills in
[gate-drills.log](gate-drills.log) show each of those gates fails on a violation.

## ci.yml

| Done-when | Where | Verdict |
|---|---|---|
| M6A-01 pushes run only on main | `on: push: branches: [main]` (9-10), `pull_request`, and `workflow_dispatch` (12) to run any branch by hand | met |
| M6A-01 a PR concurrency group cancels in-progress runs | `concurrency: group: ci-<PR number or ref>`, `cancel-in-progress` only for `pull_request` (17-20): main's runs all finish | met |
| M6A-01 every job has `timeout-minutes` | lint 10 (28), types 10 (60), test 20 (92), coverage 10 (163), distro 30 (202), gnome 20 (219); the slowest job seen in recent runs took 4 min 5 s (macOS tests) | met |
| M6A-01 actions pinned, `persist-credentials: false` | every `uses:` is a 40-hex commit with its version; every checkout has `persist-credentials: false`; zizmor reports nothing | met |
| M6A-01 ruff, pytest and Qt pinned | `lint` and `types` install `requirements-dev.txt`, the tests `requirements-test.txt`, both `--require-hashes` (128, 176) | met |
| M6A-01 pytest-timeout, `-rs`, warnings as errors, strict markers | `pyproject.toml`'s `[tool.pytest.ini_options]`; the tests run plain `pytest` so they apply | met |
| M6A-01 `wayland-protocols` and `libwayland-dev` | the Linux apt list (120), with `dbus`, `dbus-x11`, `xvfb` and `libxtst6` (M1B's, M3's and M4B's tests); the tests run under `xvfb-run -a` on Linux (135) | met |
| M6A-04 every OS's coverage combined, written to the job summary | `COVER` true on the 3.14 legs (101): Windows, macOS, Ubuntu Arm; each uploads `.coverage.*` (hidden files included); `coverage` combines, writes the markdown table to `$GITHUB_STEP_SUMMARY` (188-189) and keeps the report's exit status, so it fails below `fail_under` | met |
| M6A-05 a 3.14 leg on the shipped Qt | `include:` 3.14 on windows-latest, macos-latest (88-89); every leg installs `requirements-test.txt`, which locks requirements.txt's Qt (tests/test_requirements.py) | met |
| M6A-05 an `ubuntu-24.04-arm` leg | 90; the apt fallback picks kernel.org's `ubuntu-ports` mirror off amd64 | met |
| M6A-12 actionlint and zizmor | `lint`: actionlint from its release tarball, checked against its SHA-256, with the runner's shellcheck; then `zizmor --no-online-audits --format github .github`; both `if: !cancelled()` so they report even when ruff fails | met |
| M6A-13 mypy with `--platform` legs | `types` matrix linux, win32, darwin | met |
| M6A-03 the distributions' own PyQt6 | `distro` matrix ubuntu:24.04, debian:trixie, fedora:44, each `docker run ... sh /src/.github/scripts/distro-tests.sh` | met |
| M6A-15 test jobs without `art/` and `docs/` | `types`, `test`, `distro`, `gnome`: non-cone sparse checkout `/*`, `!/art/`, `!/docs/` (65, 107, 207, 224), which actions/checkout fetches as a partial clone; `coverage` takes only `chatmon/`, `packaging/` and `pyproject.toml`; `lint` keeps the full tree because ruff checks `art/tools` | met |

## packages.yml

| Done-when | Where | Verdict |
|---|---|---|
| M6A-07 a tag push uploads to a draft release, published at the end | `on: push: tags: ["v*"]` (13-14), no `release:` trigger; `publish` (496) runs on the push only, after `checksums` and `attest`: `gh release create TAG dist/* --draft --verify-tag` with the changelog's notes (533), checks the draft's assets are exactly `dist/`'s files, then `gh release edit --draft=false` (538). A rerun finishes an existing draft and stops at a published one (530) | met |
| M6A-07 `actions/attest-build-provenance` runs | `attest` (475) with `id-token: write` and `attestations: write` only (482-483), `subject-path: dist/*` (490), every package plus `SHA256SUMS.txt` and its signature | met |
| M6A-06 build dependencies hash-locked, `--require-hashes` | the wheel job (57), Windows and macOS (88-89: the build list first, then Nuitka's source and the rest `--no-build-isolation`), test-signed-windows (291) | met |
| M6A-06 setuptools pinned | the wheel is built `--no-isolation` with requirements-build.txt's setuptools 84.2.1 | met |
| M6A-06 `SOURCE_DATE_EPOCH` set | the `&source-date` step (56), reused in windows, macos and linux before they build | met |
| M6A-08 the wheel job runs `twine check` | 59, `--strict`; then tests/test_package_data.py with `CHATMON_DIST: dist` (62) | met |
| M6A-I1 the Linux job runs `test-install-update.sh` | 373 (ubuntu, debian: the .deb), 382 (fedora: the .rpm), after install and smoke, before removal | met |
| M6A-I1 the checksums job reads the key where it lives | sparse checkout of `chatmon/releasecheck.py` (440), grep there (462) | met |
| Drafts never mistaken for the last release | the three "last release" lookups select `(.draft \| not)` (110, 322, 390) | met |
| M1A's macOS checks | install-update inside the app, the app root's (334), and `verify-update` refusing unreadable files with 3 (336) | met |
| Time limits, pins, credentials | every job already had `timeout-minutes`; the new `attest` 10 and `publish` 15; all actions pinned; every checkout without credentials | met |

## What only a real run will show

- CI's first run on GitHub, each job's duration against its limit, and the Arm runner's apt mirror.
- The first tagged release: the draft, the attestations, and publishing.
- The Linux packages job with `test-install-update.sh` (M1A ran the script in containers itself).

These are pending operations in the plan's checkpoint.
