# M6A's manual criteria, the plans round for v0.10.0: the workflows at 7816159 and their runs (2026-11-15)

The final round's review is [../wave4f/ci-review.md](../wave4f/ci-review.md), against 45a17b3 and PR #18's runs.
Its receipt went stale because files this plan binds changed. `ci.yml` and `packages.yml` are unchanged since bf9d8ac
(`git diff bf9d8ac 7816159 -- .github/workflows/ci.yml .github/workflows/packages.yml` is empty), so every line number
below is the final round's. This review reads each criterion again against them, and then against what ran on
7816159. Job lists and every log are in [../../wave5/ci/](../../wave5/ci/):

- **main's CI run 43778643147** (push of 7816159, PR #22's merge). All 19 jobs succeeded: lint, types ×3, test ×9,
  distro ×3, gnome, coverage and sway. Every job checked out 7816159 itself
  ([../../wave5/ci/checkout.txt](../../wave5/ci/checkout.txt)).
- **Packages run 43778675599** (push of the tag v0.10.0, an annotated tag "Chatmon 0.10.0" on 7816159). All ten jobs
  succeeded: python, windows, macos (macos-latest and macos-15-intel), linux, sign-windows, test-signed-windows,
  checksums, attest and publish. This is the first tagged run of the release jobs (P-RELEASE).

| Criterion | At 7816159, and in the runs | Result |
|---|---|---|
| **M6A-01.A2**: every job has timeout-minutes; a pull request's newer run cancels its older one; pushes only on main, with workflow_dispatch for any branch; the Linux legs install the Wayland, D-Bus and X pieces and run under xvfb-run | `ci.yml` is unchanged. `on:` (pushes to `main` only, line 10) and `concurrency` (17-20) are as reviewed. `timeout-minutes` is set on lint (28), types (60), test (92), coverage (163), distro (202), sway (221) and gnome (260). The test job's apt list and `xvfb-run -a` (135) are unchanged. Run 43778643147 is a push to `main`. | pass |
| **M6A-04.A2**: each OS's Python 3.14 leg runs under coverage and uploads its data; the coverage job combines them, writes the table to the summary and fails below the floor | The three 3.14 legs uploaded their data: Windows 2 files (504396 bytes), macOS 2 (407118), ubuntu-24.04-arm 1 (414378). The coverage job's table ends `TOTAL 20941 2290 6412 943 86.4%`, against `fail_under = 84`. The same files, downloaded and combined here, give the same total ([coverage-combined.log](coverage-combined.log)). G-coverage-floor's drill, on that combined data, shows the job fails below the floor ([gate-drills.log](gate-drills.log)). | pass |
| **M6A-05.A2**: Python 3.14 legs on windows-latest, macos-latest and ubuntu-24.04-arm; every pip leg installs requirements-test.txt with --require-hashes | The run has all three 3.14 legs. Every test leg, the coverage job and the sway job install `packaging/requirements-test.txt` with `--require-hashes`. | pass |
| **M6A-15.A1**: the test, types, distro and gnome jobs check out sparsely without art/ and docs/, and the suite passes without them | The sparse-checkout patterns are unchanged (65, 107, 168, 207, 265), and the sway job's (226). Every job passed on those checkouts. | pass |
| **M6A-07.A1**: a pushed v* tag builds, signs, attests every file, drafts the release with every file, checks it and only then publishes; a rerun finishes a draft and never changes a published release | `packages.yml` is unchanged; Packages run 43778675599 ran every job on the tag. See below. | pass |
| **M6A-I1.A2**: a .deb and an .rpm each install, start, pass test-install-update.sh and are removed without a trace | Packages run 43778675599, job linux. The deb (ubuntu:24.04, debian:trixie) and the rpm (fedora:44) each printed "test-install-update: all good" (log lines 244, 273, 827). The step's `test ! -e /usr/lib/chatmon` after each removal held, and the job succeeded. | pass |

## M6A-07.A1: the first tagged release (P-RELEASE)

What Packages run 43778675599 did on the tag. Its job logs are `pkg-*` in [../../wave5/ci/](../../wave5/ci/), and
the release as published is in [outcomes.log](outcomes.log):

- **Built.** python, windows, both macos jobs and linux built every file.
  - The python job dated the build by the commit (`SOURCE_DATE_EPOCH: 1794787737`), and `twine check` PASSED the
    wheel and the sdist. `tests/test_package_data.py` then passed, 5 of 5, on what was built.
- **Signed.** sign-windows signed the installer (environment `release`, packages.yml line 167). test-signed-windows found the
  installer, its uninstaller, `chatmon.exe` and `chatmonw.exe` "signed: Valid", by the owner's certificate, each
  timestamped.
  - checksums wrote `SHA256SUMS.txt` and signed it (`SHA256SUMS.txt.sig`). Every file downloaded from the release
    matches it (`sha256sum -c`: 9 of 9 OK).
- **Attested.** attest ran `actions/attest-build-provenance` (packages.yml line 490) on `dist/*`: "Attestation created for 11
  subjects", logged in Rekor and uploaded to the repository.
  - `gh attestation verify` passed for each of the 11 files downloaded from the release. Each is SLSA provenance v1
    from `packages.yml@refs/tags/v0.10.0`, with source digest 7816159.
- **Drafted, checked, published.** publish took the "no release yet" branch. It created the release as a draft
  (`releases/tag/untagged-a984ddbfa35313d8ab75`, publish's log line 258) with every file and the changelog's notes. It checked
  that the draft held exactly the files in `dist`, and only then published it (`releases/tag/v0.10.0`, log line 259).
  - GitHub reports v0.10.0 published at 2026-11-16T00:37:23Z, not a draft and not a prerelease, with 11 files.
- **A rerun.** The "finishes a draft and never changes a published release" branch (the publish step's script,
  printed at log lines 229-232) didn't run, as the first run published. It is as reviewed in earlier rounds.

P-RELEASE is resolved: observed, and as the criterion asks.
