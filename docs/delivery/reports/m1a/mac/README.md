# M1A's macOS drill, on the owner's MacBook Pro (2026-11-15)

AC-01-MACOS's red drill needed a Mac: `ditto`, BSD `find` and the root script as macOS runs it. The owner approved
his MacBook Pro for it on 2026-11-15 ("yeah use the macbook pro"). It ran there over ssh from the Windows
workstation, twice the same day, and went green, red and green again both times:

- first on **3586a0d** (`improve/assessment-fixes`), in [3586a0d/](3586a0d/). That receipt was bound in this branch's
  commit 511c145, but plans3 re-bound M1A at 3586a0d at the same time, for ROADMAP.md's round-three amendment. The merge
  took plans3's plan.
- then on **a4fe9f8**: this branch with `improve/assessment-fixes` merged in (cbeed17, the toast merge, and 86e84e0,
  the quit guard). Those change none of M1A's files. The logs at the top of this folder are this run.

The plan's receipt is MAC-RED-AC-01-MACOS, from the second run, bound onto plans3's plan with
`docs/delivery/reports/wave4/bind.py` and [bindings.json](bindings.json). With it, T-03-macos-root and every other M1A
task is verified. The plan passes readiness, closure and resume validation ([validate-readiness.txt](validate-readiness.txt),
[validate-closure.txt](validate-closure.txt), [validate-resume.txt](validate-resume.txt)), against the Windows
profile observed for it ([context.json](context.json), [context-windows-observed.log](context-windows-observed.log)).

Only the ledger changed: the new receipt, T-03-macos-root's status and evidence, and the checkpoint. The deferred
W4-, W4B- and W4C-RED-AC-01-MACOS stay as history. The plan's narrative still says this drill needs a Mac. The scope
fingerprint hashes the narrative, so editing it would make all of the plan's receipts stale. The checkpoint's
`next_action` says so, for the next round that re-binds the plan.

## Where it ran

- macOS 15.7.9 (24G830), Intel x86_64, with the owner signed in at the console.
- Homebrew's Python 3.13.7, which was already installed, in a venv of its own with `packaging/requirements-test.txt`
  (`--require-hashes`): PyQt6 6.11.0 (Qt 6.11.2), pytest 9.2.0. Every version is in
  [context-observed.txt](context-observed.txt).
- The code: `git archive --format=tar.gz HEAD`, unpacked into `~/chatmon-drills-tmp/src`. That folder was made a git
  work tree with every file in its index (no commit), so `tests/drills/run.py` could list its files. It copied 310,
  as it does here. In the second run, the index's tree was a4fe9f8's own (`6fa4a57f`).
- This drill needs no window server, so it ran over plain ssh. M4B's drills and the full suite needed the owner's
  Aqua session, and ran there through [aqua.sh](aqua.sh).
- Everything stayed in `~/chatmon-drills-tmp`, which was removed after each run. [job.sh](job.sh) runs each step with
  `HOME` and `TMPDIR` in that folder, so nothing a test writes through them reaches the owner's own folders. pip read
  none of his configuration and kept no cache.

## The drill

[drill-spec.json](drill-spec.json), run with `sh job.sh drills SPEC LOG` ([drills.log](drills.log),
[drills-results.json](drills-results.json), [drills-run.txt](drills-run.txt)):

| Drill | Mutation in `chatmon/updates.py` (`_MACOS_ROOT`) | Red |
|---|---|---|
| MAC-AC-01-MACOS-writable | `-o -perm +022` becomes `-o -name nothing` | `test_mac_an_app_others_could_change_is_never_run_as_root` fails in its body, at `tests/test_install_update.py:287`. The root script exits 0 (`returncode=0, stdout='', stderr=''`): it ran the copied app's `install-update` and installed. The test asserts 3 and the refusal. |
| MAC-AC-01-MACOS-plan-text | `! -user root -o -perm +022` becomes `-name nothing` (the plan's own text) | The same test errors at setup: `'! -user root' isn't in the script any more`. |

Both went green, red (pytest's exit 1) and green again. Each time, the file's bytes were put back and checked by
SHA-256 (a619e20d…, as committed).

**Why the receipt binds the first one.** The plan's text (W4-, W4B- and W4C-RED-AC-01-MACOS) also removes
`! -user root`. The test's fixture puts the test user's uid in place of `root` there, and it checks that text is still
in the script before it uses it. So the plan's mutation is stopped by that check, before the root script runs. That
proves the fixture's guard, not the ownership check. MAC-AC-01-MACOS-writable keeps the text and removes only the
half the test exercises, and the test fails on its own assertion.

**What no drill here covers.** The `! -user root` half can't be drilled by this test. Every file in its copy of
Chatmon.app belongs to the test user, and only root can give a file to someone else. That half has no test that
would notice it going. Packages' macOS jobs show only that the .pkg installs Chatmon.app as root's, which is what
that half expects.

**Earlier runs**, all in [3586a0d/](3586a0d/). In the first ([drills-attempt1.log](3586a0d/drills-attempt1.log) and
the files beside it), the harness reported both drills as FAIL. The tests failed just as they did later, but the spec
expected pytest's `FAILED …`/`ERROR …` summary lines, and `pyproject.toml`'s `-rs` prints only skips. The spec now
names lines pytest does print: the assertion's location and its message. The second and third runs passed. The second
was before the setup indexed `src/` for the suite's sake (see M4B's README). The drills don't depend on that, because
the harness lists the same 310 files either way. [3586a0d/drills.log](3586a0d/drills.log) is the third run, and
3586a0d/'s `bindings.json`, `context*` and `validate-*.txt` are what it was bound and checked with in 511c145.

## What was left as found

[state.sh](state.sh) reads what the drills could have touched. It ran before and after the first session
([3586a0d/state-before.txt](3586a0d/state-before.txt), [3586a0d/state-after.txt](3586a0d/state-after.txt)), and
before and after the second ([state-before.txt](state-before.txt), [state-after.txt](state-after.txt)). Between the
two sessions, on the owner's decision, Homebrew installed Python 3.15.2. That is the only difference between the first
session's "after" and the second's "before": `python3` and `pip3` now point at 3.15, and there are 155 formulae.
[../../m4b/mac/README.md](../../m4b/mac/README.md) has the M4B drills, the full suite, the clean-up and the Python
install.
