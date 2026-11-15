# M1A's macOS drill, on the owner's MacBook Pro (2026-11-15)

AC-01-MACOS's red drill needed a Mac: `ditto`, BSD `find` and the root script as macOS runs it. The owner approved
his MacBook Pro for it on 2026-11-15 ("yeah use the macbook pro"). It ran there over ssh from the Windows
workstation, on **3586a0d** (`improve/assessment-fixes`), and it went green, red and green again. The plan's receipt
is MAC-RED-AC-01-MACOS, bound with `docs/delivery/reports/wave4/bind.py` and [bindings.json](bindings.json). With it,
T-03-macos-root and every other M1A task is verified. The plan passes closure and resume validation
([validate-closure.txt](validate-closure.txt), [validate-resume.txt](validate-resume.txt)), against the Windows
profile observed for it ([context.json](context.json), [context-windows-observed.log](context-windows-observed.log)).

Only the ledger changed: the new receipt, T-03-macos-root's status and evidence, and the checkpoint. The deferred
W4-/W4B-RED-AC-01-MACOS stay as history. The plan's narrative still says this drill needs a Mac. The scope
fingerprint hashes the narrative, so editing it would make all of the plan's receipts stale. The checkpoint's
`next_action` says so, for the next round that re-binds the plan.

## Where it ran

- macOS 15.7.9 (24G830), Intel x86_64, with the owner signed in at the console.
- Homebrew's Python 3.13.7, already installed, in a venv of its own with `packaging/requirements-test.txt`
  (`--require-hashes`): PyQt6 6.11.0, pytest 9.2.0. Every version is in [context-observed.txt](context-observed.txt).
- The code: `git archive --format=tar.gz HEAD` of 3586a0d, unpacked into `~/chatmon-drills-tmp/src`. That folder
  was made a git work tree with every file in its index (no commit), so `tests/drills/run.py` could list its files.
  It copied 310, as it does here.
- This drill needs no window server, so it ran over plain ssh. M4B's drills and the full suite needed the owner's
  Aqua session, and ran there through [aqua.sh](aqua.sh).
- Everything stayed in `~/chatmon-drills-tmp`, removed afterwards. [job.sh](job.sh) runs each step with `HOME` and
  `TMPDIR` in that folder, so nothing a test writes through them reaches the owner's own folders. pip read none of
  his configuration and kept no cache.

## The drill

[drill-spec.json](drill-spec.json), run with `sh job.sh drills SPEC LOG` ([drills.log](drills.log),
[drills-results.json](drills-results.json), [drills-run.txt](drills-run.txt)):

| Drill | Mutation in `chatmon/updates.py` (`_MACOS_ROOT`) | Red |
|---|---|---|
| MAC-AC-01-MACOS-writable | `-o -perm +022` becomes `-o -name nothing` | `test_mac_an_app_others_could_change_is_never_run_as_root` fails in its body, at `tests/test_install_update.py:287`. The root script exits 0 (`returncode=0, stdout='', stderr=''`): it ran the copied app's `install-update` and installed. The test asserts 3 and the refusal. |
| MAC-AC-01-MACOS-plan-text | `! -user root -o -perm +022` becomes `-name nothing` (the plan's own text) | The same test errors at setup: `'! -user root' isn't in the script any more`. |

Both went green, red (pytest's exit 1) and green again. Each time, the file's bytes were put back and checked by
SHA-256 (a619e20d…, as committed).

**Why the receipt binds the first one.** The plan's text (W4-/W4B-RED-AC-01-MACOS) also removes `! -user root`.
The test's fixture puts the test user's uid in place of `root` there, and it checks that text is still in the script
before it uses it. So the plan's mutation is stopped by that check, before the root script runs. That proves the
fixture's guard, not the ownership check. MAC-AC-01-MACOS-writable keeps the text and removes only the half the
test exercises, and the test fails on its own assertion.

**What no drill here covers.** The `! -user root` half can't be drilled by this test. Every file in its copy of
Chatmon.app belongs to the test user, and only root can give a file to someone else. That half has no test that
would notice it going. Packages' macOS jobs (W4B-BEH-PKG-MACOS) show only that the .pkg installs Chatmon.app as
root's, which is what that half expects.

**Earlier runs.** The drills ran three times. In the first ([drills-attempt1.log](drills-attempt1.log),
[drills-attempt1-results.json](drills-attempt1-results.json), [drills-attempt1-run.txt](drills-attempt1-run.txt)),
the harness reported both as FAIL. The tests failed just as they did later, but the spec expected pytest's
`FAILED …`/`ERROR …` summary lines, and `pyproject.toml`'s `-rs` prints only skips. The spec now names lines
pytest does print: the assertion's location and its message. The second run passed. It was before the setup
indexed `src/` for the suite's sake (see M4B's README), which the drills don't depend on: the harness lists the same
310 files either way. The logs here are the third run. Its job.sh differed from the one here only in the observe
step, which now also prints the Qt version that runs.

## What was left as found

[state.sh](state.sh) reads what the drills could have touched, before ([state-before.txt](state-before.txt)) and
after ([state-after.txt](state-after.txt)). The M4B drills and the full suite ran in the same session.
[../../m4b/mac/README.md](../../m4b/mac/README.md) has those results and the clean-up.
