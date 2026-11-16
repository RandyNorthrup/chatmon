# Outcome of the 0.10.0 delivery, 2026-11-15

This file holds the delivery's status. It supersedes the *Outcome* section of [ROADMAP.md](ROADMAP.md), which
stops at **3586a0d** (wave 4's round three). Everything else in ROADMAP.md stands: the owner decisions, the rules for
every worker, the evidence rules and the rule amendments.

**Why the Outcome moved here.** ROADMAP.md is a rule of all thirteen plans: every receipt binds its bytes. Any edit to
it makes every receipt of every plan stale, not only the receipts bound to the files a merge changed. That would
stale M1A's and M4B's macOS evidence from the owner's MacBook Pro and M4B's toast evidence from testpc2's desktop,
which can't be run again from this workstation. No plan binds this file. Each plan's `--snapshot` lists the same
bound paths before and after it was written, and this file is not among them
([reports/wave4e/snapshot-before-outcome.txt](reports/wave4e/snapshot-before-outcome.txt),
[reports/wave4e/snapshot-after-outcome.txt](reports/wave4e/snapshot-after-outcome.txt)).

## Status at 56caddd: v0.10.0 (7816159) and two fixes since

`main` at **7816159** is PR #22's merge, on top of PR #18's (65ed989, the delivery at 45a17b3). PR #22 merged three
branches:

- `wave5/compositors`: the KDE and Hyprland overlay fixes;
- `wave5/screen-readers`: the screen-reader fixes;
- `wave5/pins`: the Dependabot replacement.

main's CI run 43778643147 on 7816159 passed all 19 jobs, each on 7816159 itself
([reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)).

This round's branch, `wave5/plans-release` (PR #24), adds two of the coordinator's commits on 7816159:

- **df3e93c**: `chatmon/layer.py`'s two `QGuiApplication.instance()` calls typed (the mypy finding below), and
  CONTRIBUTING.md's opt-in table naming `CHATMON_PINS_NETWORK`.
- **56caddd**: `tests/test_app_smoke.py::test_hide_menu_and_reload` waits for the greeting (the WSL flake below).

PR #24's CI run 43794815103 on 56caddd passed all 19 jobs, after one re-run (below). Its test merge has 56caddd's own
tree ([reports/wave5b/ci/merge-tree.txt](reports/wave5b/ci/merge-tree.txt)).

**The release.** `v0.10.0` is an annotated tag ("Chatmon 0.10.0") on 7816159. Its Packages run 43778675599 passed all
ten jobs:

- the builds: python, windows, both macos and linux;
- sign-windows and test-signed-windows: the installer, its uninstaller and both executables "signed: Valid";
- checksums;
- attest: 11 subjects;
- publish: drafted with every file, checked, then published.

The release was published at 2026-11-16T00:37:23Z, not a draft, with 11 files. Every file matches the signed
`SHA256SUMS.txt`, and `gh attestation verify` passed for each: SLSA provenance from
`packages.yml@refs/tags/v0.10.0`, source 7816159
([reports/m6a/wave5/outcomes.log](reports/m6a/wave5/outcomes.log),
[reports/m6a/wave5/ci-review.md](reports/m6a/wave5/ci-review.md)).

**The plans round** ([reports/wave5/](reports/wave5/), branch `wave5/plans-release`). At 7816159, nine plans had
stale receipts, from PR #22's files: M0, M2, M3, M4A, M6A, M6B, M7, M8 and M10
([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). M1A, M1B, M4B and M5 still validated and
are byte for byte as they were.

Each of the nine gained a section for this round. A plan's prose is in every receipt's scope, so every check of each
ran again on 7816159 or was read from CI. That covers:

- the whole suite on Windows (1293 passed, 225 skipped: [reports/wave5/suite-windows.log](reports/wave5/suite-windows.log));
- the whole suite in WSL Arch with UPower on the system bus, twice. It failed both times on different timing-sensitive
  tests, each of which passes alone (below);
- every drill of those plans, on Windows and in WSL;
- the gate drills, the real sway and Orca runs, the overlay's memory check, the locks, mypy with 6.11's and 6.12.1's
  stubs, the distro drill and the reproducible wheel.

At 7816159 every check passed except two findings, below: mypy with 6.12.1's stubs, and the WSL suite's flaky tests.
Two drills' lines had moved with PR #22, and each was re-aimed at the same defect:

- **M0-12-ask-sent**, now `-v2`: `chatmon ask` keeps `_send`'s answer.
- **M3-RC-clipboard**, now `-v3`: `layer.py` sets Qt's clipboard a second way. `-v2`, which took out only the first
  line, left the real sway's clipboard test green, so `-v3` takes out both lines.

One M4A drill (AC-03-sleep-wake) crashed in its green run, inside pytest's summary hook after its test had passed.
Run again on its own, it went green, red and green.

M6B's 55 round-two receipts (all stale) were moved, byte for byte, to
[reports/m6b/history/](reports/m6b/history/README.md), as its 108 oldest were in the final round.

**Bound again at 56caddd** ([reports/wave5b/](reports/wave5b/)). The two fixes staled seven plans: M0, M3, M6A, M6B,
M7, M8 and M10 ([reports/wave5b/stale-at-56caddd.md](reports/wave5b/stale-at-56caddd.md)). Each plan's section gained a
paragraph, and every check of each ran again on 56caddd:

- the suite on Windows (1293 passed, 225 skipped);
- every drill, on Windows and in WSL, with M3-RC-clipboard-v3 in -v2's place;
- every gate drill;
- the real sway and Orca;
- mypy with both stubs;
- the how-to's replay;
- the distro drill;
- PR #24's CI run.

All of them passed. For the M6A receipts whose files didn't change, the tagged Packages run and Pins run 43778643021
were read again. M6B's 56 round-three receipts were moved to its history first, for the plan limit. The failed
receipts of the first binding stay as history.

**The finding, fixed in df3e93c: mypy with PyQt6 6.12.1's stubs failed on two of PR #22's lines.** At 7816159, on
linux, win32 and darwin, in WSL and here, mypy 2.4.1 with 6.12.1's stubs found
`chatmon/layer.py:824: error: Need type annotation for "app"  [var-annotated]`, and `:917` the same
([reports/m10/wave5/mypy-6121.log](reports/m10/wave5/mypy-6121.log),
[reports/m6a/wave5/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5/mypy-pyqt6-6.12.1-linux.log)).

- **Where.** Both lines are `app = QGuiApplication.instance()`, in `_watch_qt_focus` and `close`. They were added by
  the KWin and Hyprland fixes (6f7dd3f).
- **Why.** 6.12.1's stubs type the static `instance()` as returning `Self`. CONTRIBUTING.md's second workaround
  covers exactly this ("a value from a static constructor ... is given its type"), and these two lines don't use it.
- **Why CI is green.** Its types jobs lock 6.11's stubs, and the release's own gates also ran mypy with 6.11's only.

At 7816159 it failed:

- M10-03.A1 (the 6.12.1 half) and M10-03.A3 (the how-to's replay found the same);
- M6B-02.A1 (the 6.12 half);
- M6A-10.A1, because CONTRIBUTING.md says mypy "also passes with the next PyQt6's stubs (6.12.1)".

That is the same pattern as round three, on another line. Those receipts were recorded as failing, and the tasks behind
them blocked.

The coordinator's **df3e93c** fixes it with two type annotations,
`app: QCoreApplication | None = QGuiApplication.instance()`, and no change at run time, so no release is needed for it.
At 56caddd mypy with 6.12.1's stubs finds no issues on linux, win32 and darwin, in WSL
([reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log)), here
([reports/m10/wave5b/mypy-6121.log](reports/m10/wave5b/mypy-6121.log)) and in the how-to's replay. M10's five gate drills
go green, red and green again, and the how-to and docs reviews pass. The blocked tasks are verified again: T7B (M6A),
T4-mypy, T6-phase-b and T7-leftovers (M6B), and T3-qt612-types (M10).

**M6A's requirement M6A-02 changed, by the owner's decision.** M6A-02 said "Dependabot keeps github-actions and pip
dependencies up to date". Dependabot's first run on `main` opened #19, #20 and #21. Each locked our
`uv pip compile --universal` lists again with pip-compile for one platform, and dropped the macOS build's packages and
nuitka's Windows marker. The owner closed all three, each with a comment. PR #22 took both pip entries out of
`.github/dependabot.yml`, which keeps only github-actions. In their place is `packaging/pins.py`, run each Monday by
`.github/workflows/pins.yml`. It asks uv what each lock would move to under the same 14-day rule, and keeps one issue
while something can. On `main`, dispatched run 43778713259 opened #23 (nuitka 4.3.1 → 4.3.4, PyQt6 6.12.0 held
back), and run 43778794994 edited #23 in place, with no second issue. The re-run of M6A-02.A1 fails as written, and is
recorded as a failed receipt. M6A-02 is superseded by M6A-02B (Dependabot for actions, the pins check for Python),
with three criteria that all pass, and T7 by T7B
([reports/m6a/wave5/pins-review.md](reports/m6a/wave5/pins-review.md)). The coordinator confirmed the replacement. T7B
also carries M6A-10.A1, which passes again since df3e93c.

**The WSL suite's flaky tests, a second finding.** At 7816159 the whole suite in WSL failed twice, each time on
different tests:

- Beside the Windows runner's drills: 5 failed and 1 errored ([reports/wave5/suite-linux.log](reports/wave5/suite-linux.log)).
  sway's click test timed out at setup, in `shutil.which` over a PATH of `/mnt/c` folders. The hook smoke test
  failed, and so did four headless KWin and Hyprland checks.
- On a quiet machine: 1 failed, `test_app_smoke.py::test_hide_menu_and_reload`
  ([reports/wave5/suite-linux-quiet.log](reports/wave5/suite-linux-quiet.log)).

Each passed alone, and `tests/test_app_smoke.py` passed five runs in five on its own. In CI the smoke tests pass on
every leg, and the sway test in the sway job; the compositor checks skip there. These are tests whose waits are too
short for WSL's `/mnt/c` tree, not product behaviour. M3 keeps both runs as failed receipts.

**56caddd** fixes the quiet run's failure. The greeting, 1.5 s after start, could land inside
`test_hide_menu_and_reload`'s one-second spin when the companion started slowly, and add "Recent messages". The test
now waits for it.

- **The coordinator's drill**, run again here, fails the old body with the start slowed by 0.6 s and passes the new
  one at 0, 0.6, 1.4 and 2 s, on Windows and in WSL
  ([reports/wave5b/flaky-hide-menu-drill-windows.log](reports/wave5b/flaky-hide-menu-drill-windows.log),
  [-wsl.log](reports/wave5b/flaky-hide-menu-drill-wsl.log)).
- **The whole WSL suite**, retried at 56caddd on a quiet machine: 1391 passed, 127 skipped, exit 0
  ([reports/wave5b/suite-linux.log](reports/wave5b/suite-linux.log)), now a passing receipt in M3.

**A CI flake on macOS.** PR #24's CI run 43794815103 first failed one test on macOS 3.15:
`tests/test_app_smoke.py::test_greets_and_reacts_to_agents`, waiting at line 30 for an agent's alert to show after the
greeting ([reports/wave5b/ci/ci-133061193367-test-macos-latest-3.15.log](reports/wave5b/ci/ci-133061193367-test-macos-latest-3.15.log)).
56caddd didn't touch that test, and the job's re-run passed. It is another wait that a slow runner can outlast, beside
the WSL ones: a note for the coordinator.

Every plan was validated at resume and at closure on 56caddd
([reports/wave5b/validation-sweep.txt](reports/wave5b/validation-sweep.txt); the first binding's, at 7816159, is
[reports/wave5/validation-sweep.txt](reports/wave5/validation-sweep.txt)). Twelve close; M10 stops only on
P-CI-NEXT-STUBS, which is not a criterion. No receipt of any plan is stale
([reports/wave5b/stale-after-binding.md](reports/wave5b/stale-after-binding.md)).

| Milestone | State | What's left, and who |
|---|---|---|
| M0 App core | closed | Nothing. |
| M1A Security, updates | closed | Nothing. The macOS root drills ran on the owner's MacBook Pro (wave4/mac-drills, wave4/mac-owner). |
| M1B Brains, stored data | closed | Nothing. |
| M2 Bubbles, ask box | closed | Nothing. |
| M3 Stage, overlay | closed | Nothing. |
| M4A Platform awareness | closed | Nothing. |
| M4B Hotkey, sound, toasts | closed | Nothing. AC-00C, AC-01D and AC-02F were drilled on the MacBook Pro, and AC-03E on testpc2's desktop. |
| M5 Reminders, offline, locale | closed | Nothing. |
| M6A CI and tooling | closed | Nothing. P-RELEASE and P-DEPENDABOT are observed and recorded, and M6A-02 is superseded by M6A-02B, as the coordinator confirmed. |
| M6B Static analysis, logging | closed | Nothing. |
| M7 Integration | closed | Nothing. |
| M8 Translation | closed | Nothing. |
| M9 Sounds (coordinator) | done | The owner accepted the cues as they are (2026-11-14). |
| M10 Follow-ups | checkpoint | Every task is verified. One pending operation, not a criterion: **P-CI-NEXT-STUBS**, from 2026-11-28, when PyQt6 6.12.1 can be hash-locked: the `types` job's check against the next stubs (integration note 2), which would have caught layer.py's two lines in CI, the coordinator. |
| Consolidation | done | v0.10.0 is released. |

## Before the release, beyond the criteria

These were the gaps a person was to close before the release. Both were worked on 2026-11-15 against 65ed989, and the
fixes are in 7816159.

- **Hyprland and KDE** ([reports/release/compositors/](reports/release/compositors/README.md)).
  `tests/test_compositors.py` runs every check of `tests/test_sway.py` on a headless KWin 6.8 and Hyprland 0.57 in
  WSL Arch, with the real Orca. It found three problems, all fixed in `chatmon/layer.py` and `chatmon/penguin.py`:
  - KWin kept the keyboard after the ask box closed.
  - Hyprland ended a quick drag.
  - KWin refused Qt's copy.

  A fourth fix covers a screen that moves under the stage. Each is guarded by a unit test CI runs and was drilled red
  (14 of 14). With the fixes, KWin and Hyprland pass all 39 checks and sway its 57. Not checked: a real Plasma or
  Hyprland desktop on a GPU, with real input devices and monitors.
- **Screen readers** ([reports/release/screen-readers/](reports/release/screen-readers/README.md),
  [fixes](reports/release/screen-readers/fixes/README.md)). The release probe ran Chatmon with real readers and kept
  what each said. It found four problems:
  - VoiceOver dropped held announcements and the greeting.
  - With VoiceOver on, typing in the ask box went nowhere.
  - On Windows, Chatmon's own stage made Windows report "busy", which held its bubbles and hid notifications.
  - `chatmon ask` didn't make Chatmon active on macOS 14 and later.

  All four are fixed, with tests and seven red drills. With the fixes:
  - **VoiceOver** (macOS 26.7.2, from source and as Chatmon.app) said the greeting, what was held 2.6-2.8 s after
    Chatmon came forward, and typed answers.
  - **NVDA 2026.3.1** said Chatmon's announcements in front (UI Automation) and its banners behind.
  - **Narrator** on testpc2 was heard by a person, the owner, against 65ed989 (13:15-13:18 PST), while Chatmon
    raised two UI Automation notifications in front. Its words couldn't be captured as text.

## Outside the criteria

- **The PyQt6 stub report** (M10's integration note 4): reported, waiting on Riverbank's fix.
  - Others had already reported the core of it on the PyQt mailing list: Veronica Berglyd Olsen on 2026-11-14
    (https://www.riverbankcomputing.com/pipermail/pyqt/2026-November/046574.html) and Dragan A. on 2026-11-15
    (.../046578.html).
  - On the owner's instruction, the coordinator posted the follow-up from the owner's subscription on 2026-11-16,
    archived at https://www.riverbankcomputing.com/pipermail/pyqt/2026-November/046579.html. It adds mypy's
    `--strict` repro, `installEventFilter`, `removeEventFilter` and `setParent` taking `Self`, and `setParent`
    losing `| None`.
  - All three were read again ([reports/m10/wave5/stub-report.log](reports/m10/wave5/stub-report.log)).
- **Plan size.** The validator reads a plan of at most 4 MiB (4,194,304 bytes), and every re-binding adds a round of
  receipts. After this round the largest are:
  - M8, 3.69 MB;
  - M7, 3.50 MB;
  - M6B, 3.46 MB, after moving round two's and round three's receipts out (55 and 56).

  The next round that re-binds M8, M7 or M6B would take it to or past the limit. Archive its oldest stale receipts
  first: M8's original `E-` receipts, M7's `RED-` and `W4-`, M6B's `W4E-`. The way out is M6B's: move a plan's oldest
  stale or failed receipts, byte for byte, to `reports/<id>/history/` with a README (where they were last, why, and
  each file's SHA-256). Take their ids out of the tasks' evidence lists, and point to the folder from the plan's next
  section ([reports/m6b/history/README.md](reports/m6b/history/README.md),
  [reports/wave5/archive_receipts.py](reports/wave5/archive_receipts.py)).
