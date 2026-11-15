## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI runs this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time. One of them, followups, is
changing packaging and the requirements. Their merges will make some of these receipts stale again.

**What the runs answered.** Every leg's result for this plan's tests is in
[reports/m1a/ci/observed.txt](reports/m1a/ci/observed.txt).

- **CI-MACOS: resolved.** In CI run 43677128712 on fb19cb9, with every job green, the macOS tests passed on all three
  macOS legs: the root code with a checked copy of Chatmon.app, the AppleScript hand-off, the postinstall under BSD
  `ls`, and the `statfs` mount check. In PR #18's Packages run 43677664360, on fb19cb9's own tree, the macos-latest and
  macos-15-intel jobs installed the built .pkg. Chatmon.app was root's, with `install-update` inside it, and its own frozen `verify-update` refused missing
  files with exit 3.
- **CI-CONTAINER: resolved.** In the same run, and in the earlier 43675230966, `packages.yml`'s Linux job ran `packaging/linux/test-install-update.sh`, root's real path,
  in ubuntu:24.04, debian:trixie and fedora:44 containers ("all good" three times), with no caller's checksum.
- **MERGE-ISOLATION: resolved.** `tests/conftest.py` gives every test its own `LOCALAPPDATA` and `CHATMON_INSTANCE`, and
  the whole suite passes on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241 passed, 148
  skipped). It passes on CI's three Windows legs too.

**What was re-run.** The plan's 17 Windows drills that still apply and its 8 Linux drills (in WSL), every one green, red
and green again. Two Windows drills mutated text that later merges rewrote. Their criteria have other drills
([wave4/drills-left-out.txt](reports/m1a/wave4/drills-left-out.txt)). AC-10's docstrings were read again against the
code ([wave4/review-ac10.md](reports/m1a/wave4/review-ac10.md)). They still hold, and `app.py`'s accept path now makes the
`client_is_me` check they offer. The requirements were reviewed again against the amended rules
([wave4/readiness.md](reports/m1a/wave4/readiness.md)).

**What remains.** AC-01-MACOS's red drill. Its behavior is now observed on macOS, but proving its test would notice the
ownership check going (`! -user root -o -perm +022` in `_MACOS_ROOT`) needs a run on macOS: `ditto`, BSD `find` and
`osascript`. No Mac is here or in the test lab, and a CI run of a drill branch needs a push, which this worker may not
make. It is recorded as a deferred red receipt, W4-RED-AC-01-MACOS, which says how to run it. T-03-macos-root stays
implemented until it is done. Owner: Randy on a Mac, or the coordinator with a throwaway drill branch on CI.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.
