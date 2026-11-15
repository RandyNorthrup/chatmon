# M6A's manual criteria, the final round: the workflows at 45a17b3 and PR #18's runs of them (2026-11-15)

Round three's review is [../wave4c/ci-review.md](../wave4c/ci-review.md), against 3586a0d's runs. Its receipt went
stale because M6A's plan gained its final-round section, and a plan's prose is in every receipt's scope. `ci.yml`,
`packages.yml` and `dependabot.yml` are unchanged since bf9d8ac (`git diff bf9d8ac 45a17b3 -- .github` is empty), so
every line number below is round two's. This review reads each criterion again against them, and then against PR
#18's own runs on 45a17b3. Those runs' test merge `eb8a996` has 45a17b3's own tree
([../../wave4e/ci/merge-tree.txt](../../wave4e/ci/merge-tree.txt)):

- **CI run 43743804662.** All 19 jobs succeeded: lint, types ×3, test ×9, distro ×3, gnome, coverage and sway.
- **Packages run 43743804716.** python, windows, macos (macos-latest and macos-15-intel) and linux succeeded.
  sign-windows, test-signed-windows, checksums, attest and publish were skipped, as designed for a run that isn't a
  tag.

Their job lists and logs are in [../../wave4e/ci/](../../wave4e/ci/).

| Criterion | At 45a17b3, and in the runs | Result |
|---|---|---|
| **M6A-01.A2**: every job has timeout-minutes; a pull request's newer run cancels its older one; pushes only on main, with workflow_dispatch for any branch; the Linux legs install the Wayland, D-Bus and X pieces and run under xvfb-run | `ci.yml` is unchanged: `on:` and `concurrency` as reviewed, and `timeout-minutes` on lint (28), types (60), test (92), coverage (163), distro (202), sway (221) and gnome (260). The test job's apt list and `xvfb-run -a` are unchanged (120, 135). Both runs are pull_request runs on PR #18. | pass |
| **M6A-04.A2**: each OS's Python 3.14 leg runs under coverage and uploads its data; the coverage job combines them, writes the table to the summary and fails below the floor | The three 3.14 legs uploaded their data: Windows 2 files (artifact of 503001 bytes), macOS 2 (404929), ubuntu-24.04-arm 1 (412775). The coverage job's log ends `TOTAL 20817 2282 6368 935 86.4%`, against `fail_under = 84`. The same files, downloaded and combined here, give the same total ([coverage-combined.log](coverage-combined.log)). G-coverage-floor's drill, on that combined data, shows the job fails below the floor. | pass |
| **M6A-05.A2**: Python 3.14 legs on windows-latest, macos-latest and ubuntu-24.04-arm; every pip leg installs requirements-test.txt with --require-hashes | The run has all three 3.14 legs. Every test leg, the coverage job and the sway job install `packaging/requirements-test.txt` with `--require-hashes`. | pass |
| **M6A-15.A1**: the test, types, distro and gnome jobs check out sparsely without art/ and docs/, and the suite passes without them | The sparse-checkout patterns are unchanged (65, 107, 168, 207, 265), and the sway job's (226). Every job passed on those checkouts. | pass |
| **M6A-07.A1**: a pushed v* tag builds, signs, attests every file, drafts the release with every file, checks it and only then publishes; a rerun finishes a draft and never changes a published release | `packages.yml` is unchanged. Packages run 43743804716 shows the non-tag half again: every build job ran and the five release jobs were skipped. No v0.10.0 tag exists; the newest is v0.9.2 ([../../wave4e/github-settings.txt](../../wave4e/github-settings.txt)). | pass for the workflow as reviewed; the tagged run is still P-RELEASE |
| **M6A-I1.A2**: a .deb and an .rpm each install, start, pass test-install-update.sh and are removed without a trace | Packages run 43743804716, job linux. The deb (ubuntu:24.04, debian:trixie) and the rpm (fedora:44) each printed "test-install-update: all good" (log lines 240, 269, 823). The step's `test ! -e /usr/lib/chatmon` after each removal held, and the job succeeded. | pass |

## M6A-02.A1 (Dependabot)

`.github/dependabot.yml` is unchanged since round two and validates against SchemaStore's Dependabot schema
([dependabot-schema.log](dependabot-schema.log)). It still has:

- three entries, each weekly with a 14-day cooldown;
- the PyQt6 groups;
- `versioning-strategy: increase-if-necessary`, which keeps the `PyQt6>=6.5` floor;
- the ignore for PyQt6 6.12.0, whose own `QtDBus.pyi` stops mypy. The criterion asks nothing about which versions to
  skip.

`main` still doesn't have the file ([../../wave4e/github-settings.txt](../../wave4e/github-settings.txt)), so
Dependabot's first run is still P-DEPENDABOT.

The `lint` job's actionlint (with shellcheck) and zizmor (v1.31.1, "completed" for `dependabot.yml`, `ci.yml` and
`packages.yml`) ran on all of these files, and the job succeeded.
