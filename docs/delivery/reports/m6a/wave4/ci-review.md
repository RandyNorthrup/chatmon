# M6A's manual criteria against the workflows' first runs (wave 4, 2026-11-14)

M6A's manual criteria are about GitHub Actions' own scheduling, runners, sparse checkouts and releases. When M6A was
delivered they could only be reviewed and linted, because nothing had run on GitHub. Two runs now have:

- **CI run 43677128712** (`ci.yml`, workflow_dispatch on improve/assessment-fixes at fb19cb9). All 18 jobs succeeded.
- **Packages run 43675230966** (`packages.yml`, workflow_dispatch at d3f6a6e, whose `.github/`, `packaging/` and build
  inputs are fb19cb9's). python, windows, macos (macos-latest and macos-15-intel) and linux succeeded. sign-windows,
  test-signed-windows, checksums, attest and publish were skipped, as designed for a run that isn't a pushed tag.

Their job lists are in [../../wave4/ci/ci-43677128712.json](../../wave4/ci/ci-43677128712.json) and
[../../wave4/ci/packages-43675230966.json](../../wave4/ci/packages-43675230966.json). Their logs are in
[../../wave4/ci/](../../wave4/ci/). Each criterion below was read again against fb19cb9's workflow files, then against
those runs. The workflows' lint (actionlint with shellcheck, zizmor) is CI's `lint` job, green in run 43677128712.

| Criterion | At fb19cb9, and in the runs | Result |
|---|---|---|
| **M6A-01.A2**: every job has timeout-minutes; a pull request's newer run cancels its older one; pushes only on main, workflow_dispatch for any branch; the Linux legs install wayland-protocols, libwayland-dev, dbus, dbus-x11, xvfb and libxtst6 and run under xvfb-run | `ci.yml`: `on: push: branches: [main]`, `pull_request`, `workflow_dispatch` (lines 8-12). `concurrency` keyed on the PR number with `cancel-in-progress` for pull requests (17-20). `timeout-minutes` on lint (28), types (60), test (92), coverage (163), distro (202) and gnome (219). The apt list (120) and `xvfb-run -a` on Linux (135). Run 43677128712 is a workflow_dispatch on a branch other than main, and its Linux legs' logs show the apt step and the tests under xvfb-run. Cancelling an older pull-request run can only be seen on a PR's second push; the setting is in place. | pass |
| **M6A-04.A2**: each OS's Python 3.14 leg runs under coverage and uploads its data; the coverage job combines them, writes the table to the job summary and fails below the floor | `COVER` is true for the 3.14 legs (101). The 3.14 legs uploaded `coverage-windows-latest-3.14` (2 files), `coverage-macos-latest-3.14` (2) and `coverage-ubuntu-24.04-arm-3.14` (1) (their logs: "With the provided path, there will be ... uploaded", "Uploaded bytes"). The coverage job downloaded `coverage-*`, combined them, wrote the table to the summary, and exits with `coverage report`'s status (174-191). Its log ends `TOTAL 20434 2270 6230 924 86.2%`, against `fail_under = 72`. The same five files, downloaded and combined here, give the same 86.2% ([coverage-combined.log](coverage-combined.log)). That the job fails below the floor is G-coverage-floor's drill. | pass |
| **M6A-05.A2**: Python 3.14 legs on windows-latest, macos-latest and ubuntu-24.04-arm; every pip leg installs requirements-test.txt with --require-hashes | The run's jobs include test (windows-latest, 3.14), test (macos-latest, 3.14) and test (ubuntu-24.04-arm, 3.14). Each test leg, and the coverage job, ran `python -m pip install --require-hashes -r packaging/requirements-test.txt` (in every test log). | pass |
| **M6A-15.A1**: the test, types, distro and gnome jobs check out sparsely without art/ and docs/, and the suite passes without them | Each of those jobs' checkout has `sparse-checkout: /* !/art/ !/docs/` with cone mode off (65, 107, 168, 207, 224). The checkout lines in the logs show the same, and git wrote `.git/info/sparse-checkout`. Every test leg, every distro job and the gnome job passed on those checkouts. | pass |
| **M6A-07.A1**: a pushed v* tag builds and signs, attest-build-provenance attests every file, publish drafts the release with the changelog's notes and every file, checks the draft holds exactly those files, and only then publishes; a rerun finishes a draft and never changes a published release | `packages.yml` at fb19cb9: `on: push: tags: ["v*"]`. `attest` uses actions/attest-build-provenance with `subject-path: dist/*`. `publish` (`if: github.event_name == 'push'`) checks the tag against the version, writes the notes from `packaging/build.py notes`, finishes an existing draft or refuses a published release, creates the draft with every file, compares the attached names with `dist/`, and only then sets `--draft=false`. Packages run 43675230966 shows the non-tag half: every build job ran and the five release jobs were skipped. The tagged half needs a pushed v* tag, which hasn't happened (P-RELEASE). | pass for the workflow as reviewed; the first tagged release is still a pending operation |
| **M6A-I1.A2**: a .deb and an .rpm built from this tree each install, start, pass packaging/linux/test-install-update.sh and are removed without a trace | Packages run 43675230966, job linux, step "Install each on a fresh system, run it, remove it". The deb in ubuntu:24.04 and debian:trixie and the rpm in fedora:44 were each installed, started (`build.py smoke`), passed `test-install-update.sh` ("test-install-update: all good", log lines 228, 256, 810) and removed, and the step's `test ! -e /usr/lib/chatmon` after each `apt-get remove` and `dnf remove` held. The job succeeded. | pass |

## M6A-02.A1 (Dependabot)

`.github/dependabot.yml` is unchanged since M6A delivered it (`9b4cdc6`). It validates against SchemaStore's Dependabot
schema again ([dependabot-schema.log](dependabot-schema.log)). Reviewed again, it still has the three entries, weekly,
with a 14-day cooldown, the PyQt6 groups, and `versioning-strategy: increase-if-necessary` on the root entry, which keeps the `PyQt6>=6.5` floor. Dependabot reads its
configuration from the default branch, and `main` doesn't have this file yet
([../../wave4/github-settings.txt](../../wave4/github-settings.txt)). Its first run is still a pending operation
(P-DEPENDABOT).

This review covers fb19cb9 only. Two other workers are changing code at the same time. The wayland worker is changing
`ci.yml`, so this review must be repeated after that merge.
