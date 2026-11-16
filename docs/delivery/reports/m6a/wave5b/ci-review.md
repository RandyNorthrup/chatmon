# M6A's manual criteria, the plans round for v0.10.0, bound again at 56caddd (2026-11-15)

This round's first review is [../wave5/ci-review.md](../wave5/ci-review.md), at 7816159: the workflows line by line,
main's CI run 43778643147, and v0.10.0's tagged Packages run 43778675599, the first run of the release jobs
(P-RELEASE, [../wave5/outcomes.log](../wave5/outcomes.log)). Since then the coordinator's df3e93c changed
`chatmon/layer.py` and CONTRIBUTING.md, and 56caddd `tests/test_app_smoke.py`. `.github/` is unchanged
(`git diff 7816159 56caddd -- .github` is empty), so every line number and every reading of the workflows in the first
review stands, and so does the release, which is 7816159's.

What ran on 56caddd: PR #24's CI run 43794815103, whose test merge has 56caddd's own tree
([../../wave5b/ci/merge-tree.txt](../../wave5b/ci/merge-tree.txt)). Its first attempt failed one test on macOS 3.15:
`tests/test_app_smoke.py::test_greets_and_reacts_to_agents`, waiting for an agent's alert after the greeting
([../../wave5b/ci/ci-133061193367-test-macos-latest-3.15.log](../../wave5b/ci/ci-133061193367-test-macos-latest-3.15.log)),
so its coverage job was skipped. The re-run of that job passed (1269 passed, 249 skipped), and so did the coverage job;
all 19 jobs are green ([../../wave5b/ci/ci-43794815103.json](../../wave5b/ci/ci-43794815103.json)).

| Criterion | At 56caddd, and in the run | Result |
|---|---|---|
| **M6A-01.A2**: every job has timeout-minutes; a pull request's newer run cancels its older one; pushes only on main, with workflow_dispatch for any branch; the Linux legs install the Wayland, D-Bus and X pieces and run under xvfb-run | `ci.yml` unchanged, as reviewed. Run 43794815103 is a pull_request run; the run before it on PR #24 (43794649782, df3e93c) was cancelled when 56caddd was pushed. | pass |
| **M6A-04.A2**: each OS's Python 3.14 leg runs under coverage and uploads its data; the coverage job combines them, writes the table to the summary and fails below the floor | The three 3.14 legs uploaded their data, and the coverage job's table ends `TOTAL 20941 2289 6412 941 86.4%`, against `fail_under = 84` ([../../wave5b/ci/ci-133065350839-coverage.log](../../wave5b/ci/ci-133065350839-coverage.log)). The same files, downloaded and combined here, give the same total ([coverage-combined.log](coverage-combined.log)). G-coverage-floor's drill, on that data, shows the job fails below the floor ([gate-drills.log](gate-drills.log)). | pass |
| **M6A-05.A2**: Python 3.14 legs on windows-latest, macos-latest and ubuntu-24.04-arm; every pip leg installs requirements-test.txt with --require-hashes | As in the first review; the run has all three 3.14 legs. | pass |
| **M6A-15.A1**: the test, types, distro and gnome jobs check out sparsely without art/ and docs/, and the suite passes without them | As in the first review; every job passed on those checkouts. | pass |
| **M6A-07.A1**: a pushed v* tag builds, signs, attests every file, drafts the release with every file, checks it and only then publishes | `packages.yml` unchanged; the first review's reading of the tagged run 43778675599 stands (no tag since). | pass |
| **M6A-I1.A2**: a .deb and an .rpm each install, start, pass test-install-update.sh and are removed without a trace | `packages.yml` and the Linux packaging unchanged; the tagged run's linux job, as in the first review. | pass |
