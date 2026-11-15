# M6A's manual criteria, round two: the workflows at bf9d8ac and PR #18's runs of them (2026-11-15)

Round one's review is [../wave4/ci-review.md](../wave4/ci-review.md), against fb19cb9's runs. This one reads each
criterion again against `ci.yml`, `packages.yml` and `dependabot.yml` at bf9d8ac. It then checks them against PR #18's
own runs on bf9d8ac, whose test merge has bf9d8ac's tree:

- **CI run 43701523023.** All 19 jobs succeeded: lint, types ×3, test ×9, distro ×3, gnome, coverage and the new
  `sway`.
- **Packages run 43701523037.** python, windows, macos (macos-latest and macos-15-intel) and linux succeeded.
  sign-windows, test-signed-windows, checksums, attest and publish were skipped, as designed for a run that isn't a
  tag.

Their job lists and logs are in [../../wave4b/ci/](../../wave4b/ci/).

| Criterion | At bf9d8ac, and in the runs | Result |
|---|---|---|
| **M6A-01.A2**: every job has timeout-minutes; a pull request's newer run cancels its older one; pushes only on main, with workflow_dispatch for any branch; the Linux legs install the Wayland, D-Bus and X pieces and run under xvfb-run | `on:` and `concurrency` are unchanged. `timeout-minutes` is set on lint (28), types (60), test (92), coverage (163), distro (202), the new sway (221) and gnome (260). The test job's apt list and `xvfb-run -a` are unchanged (120, 135). Both runs are pull_request runs on PR #18. | pass |
| **M6A-04.A2**: each OS's Python 3.14 leg runs under coverage and uploads its data; the coverage job combines them, writes the table to the summary and fails below the floor | The three 3.14 legs uploaded their data: Windows 2 files (502401 bytes), macOS 2 (405803), ubuntu-24.04-arm 1 (411923). The coverage job's log ends `TOTAL 20758 2261 6346 926 86.5%`, against `fail_under = 84`. The same files, combined here, give 86.5% ([coverage-combined.log](coverage-combined.log)). G-coverage-floor's drill shows the job fails below the floor. | pass |
| **M6A-05.A2**: Python 3.14 legs on windows-latest, macos-latest and ubuntu-24.04-arm; every pip leg installs requirements-test.txt with --require-hashes | The run has all three 3.14 legs. Every test leg, the coverage job and the sway job install `packaging/requirements-test.txt` with `--require-hashes`. | pass |
| **M6A-15.A1**: the test, types, distro and gnome jobs check out sparsely without art/ and docs/, and the suite passes without them | The sparse-checkout patterns are unchanged (65, 107, 168, 207, 265), and the sway job has them too (226). Every job passed on those checkouts. | pass |
| **M6A-07.A1**: a pushed v* tag builds, signs, attests every file, drafts the release with every file, checks it and only then publishes; a rerun finishes a draft and never changes a published release | The release jobs in `packages.yml` are unchanged since round one's review. Packages run 43701523037 shows the non-tag half again: every build job ran and the five release jobs were skipped. No v0.10.0 tag exists ([../../wave4b/github-settings.txt](../../wave4b/github-settings.txt)). | pass for the workflow as reviewed; the tagged run is still P-RELEASE |
| **M6A-I1.A2**: a .deb and an .rpm each install, start, pass test-install-update.sh and are removed without a trace | Packages run 43701523037, job linux. The deb (ubuntu:24.04, debian:trixie) and the rpm (fedora:44) each printed "test-install-update: all good" (log lines 240, 269, 823). The step's `test ! -e /usr/lib/chatmon` after each removal held, and the job succeeded. | pass |

## M6A-02.A1 (Dependabot)

`.github/dependabot.yml` validates against SchemaStore's Dependabot schema ([dependabot-schema.log](dependabot-schema.log)).
Read again, it still has:

- three entries, each weekly with a 14-day cooldown;
- the PyQt6 groups;
- `versioning-strategy: increase-if-necessary`, which keeps the `PyQt6>=6.5` floor.

Since round one it also ignores PyQt6 6.12.0, whose own `QtDBus.pyi` stops mypy, and its comment says so. The
criterion asks nothing about which versions to skip, so this changes no obligation. `main` still doesn't have the
file, so Dependabot's first run is still P-DEPENDABOT.

The `lint` job's actionlint (with shellcheck) and zizmor (v1.31.1, every workflow file "completed") ran on all of these
files, and the job succeeded.

Evidence for bf9d8ac only. Another worker (wave4/crash) may change code for an intermittent Qt crash. It doesn't own
the workflows.
