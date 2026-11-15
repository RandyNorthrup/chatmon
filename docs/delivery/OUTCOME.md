# Outcome of the 0.10.0 delivery, 2026-11-15

This file holds the delivery's final status. It supersedes the *Outcome* section of [ROADMAP.md](ROADMAP.md), which
stops at **3586a0d** (wave 4's round three). Everything else in ROADMAP.md stands: the owner decisions, the rules for
every worker, the evidence rules and the rule amendments.

**Why the Outcome moved here.** ROADMAP.md is a rule of all thirteen plans: every receipt binds its bytes. Any edit to
it makes every receipt of every plan stale, not only the receipts bound to the files a merge changed. In round three
that forced every plan's checks to be run again. Now it would also stale M1A's and M4B's macOS evidence from the
owner's MacBook Pro and M4B's toast evidence from testpc2's desktop, which can't be run again from this workstation.
No plan binds this file. Each plan's `--snapshot` lists the same bound paths before and after it was written, and
this file is not among them ([reports/wave4e/snapshot-before-outcome.txt](reports/wave4e/snapshot-before-outcome.txt),
[reports/wave4e/snapshot-after-outcome.txt](reports/wave4e/snapshot-after-outcome.txt)).

## Status at 45a17b3

`improve/assessment-fixes` at **45a17b3** has wave4/crash, the quit guard (`86e84e0`), the toast fix (`8c24b1c`),
wave4/mac-drills (`b5aa9d0`) and wave4/mac-owner (`4cc828e`) merged. PR #18's CI run 43743804662 on 45a17b3 passed all
19 jobs, and its test merge `eb8a996` has 45a17b3's own tree
([reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)). Packages run 43743804716 passed its five build jobs and skipped the five release jobs, as designed for a run
that isn't a tag ([reports/wave4e/ci/packages-43743804716.json](reports/wave4e/ci/packages-43743804716.json)).

The final round ([reports/wave4e/](reports/wave4e/)) found six plans with stale receipts, all from those merges
([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)):

- M0: `chatmon/app.py` and `tests/test_app_smoke.py`.
- M3 and M10: `chatmon/app.py`.
- M6B: the same two and `tests/test_install_update.py`.
- M7: the same two and `tests/test_wintoast.py`.
- M8: `chatmon/app.py` and `tests/test_app_smoke.py`.

Their checks ran again on 45a17b3. That covers the suite on Windows (1259 passed, 179 skipped: [reports/wave4e/suite-windows.log](reports/wave4e/suite-windows.log)) and in WSL Arch with UPower on the
system bus (1316 passed, 122 skipped: [reports/wave4e/suite-linux.log](reports/wave4e/suite-linux.log)), and every drill of those plans. CI's logs were read as evidence. Round three's two findings
are fixed and checked:

- **mypy with PyQt6 6.12.1's stubs passes.** It finds no issues on linux, win32 and darwin, here and in WSL. M10's
  five gate drills go green, red and green. M6A-10.A1, M6B-02.A1's 6.12 half and M10-03.A1's 6.12.1 half pass again.
- **The quit test passes with UPower on the bus.** `test_a_quit_companion_runs_nothing_it_had_waiting` passed in
  WSL's whole suite, then five runs in five on its own ([reports/wave4e/crash-test-wsl.log](reports/wave4e/crash-test-wsl.log)).
  A drill that takes the guard out of `Companion._heard` makes it fail there (CRASH-08, [reports/wave4e/crash/drills-heard-linux.log](reports/wave4e/crash/drills-heard-linux.log)).

Every plan was validated at resume and at closure on 45a17b3. Eleven close. M6A and M10 stop only on their pending
operations, which are outcomes of a release, a merge or a date, not criteria
([reports/wave4e/validation-sweep.txt](reports/wave4e/validation-sweep.txt)). No receipt of any plan is stale
([reports/wave4e/stale-after-binding.md](reports/wave4e/stale-after-binding.md)).

| Milestone | State | What's left, and who |
|---|---|---|
| M0 App core | closed | Nothing. |
| M1A Security, updates | closed | Nothing. The macOS root drills ran on the owner's MacBook Pro (wave4/mac-drills, wave4/mac-owner). |
| M1B Brains, stored data | closed | Nothing. |
| M2 Bubbles, ask box | closed | Nothing. |
| M3 Stage, overlay | closed | Nothing. The overlay is proven on a real sway in CI and in WSL, with the real Orca in WSL. |
| M4A Platform awareness | closed | Nothing. |
| M4B Hotkey, sound, toasts | closed | Nothing. AC-00C, AC-01D and AC-02F were drilled on the MacBook Pro, and AC-03E on testpc2's desktop. |
| M5 Reminders, offline, locale | closed | Nothing. |
| M6A CI and tooling | checkpoint | Every task is verified; M6A-10.A1 passes again, recorded without a new section in the plan, so that none of its other receipts go stale ([reports/m6a/wave4e/final-round-note.md](reports/m6a/wave4e/final-round-note.md)). Two pending operations, outcomes of a release and a merge, not criteria: **P-RELEASE**, the first tag-pushed release (v0.10.0; none yet, the newest tag is v0.9.2), Randy or the coordinator; **P-DEPENDABOT**, Dependabot's first run once `.github/dependabot.yml` is on `main`, the coordinator, after the merge. |
| M6B Static analysis, logging | closed | Nothing. |
| M7 Integration | closed | Nothing. |
| M8 Translation | closed | Nothing. |
| M9 Sounds (coordinator) | done | The owner accepted the cues as they are (2026-11-14). |
| M10 Follow-ups | checkpoint | Every task is verified. One pending operation, not a criterion: **P-CI-NEXT-STUBS**, from 2026-11-28, when PyQt6 6.12.1 can be hash-locked, the `types` job's check against the next stubs (integration note 2), the coordinator. And for the owner: the upstream report on PyQt6's stubs (note 4), which needs the owner's PyQt mailing-list account. |
| Consolidation | the coordinator's | Version 0.10.0, README and changelog. PR #18 (`improve/assessment-fixes` to `main`) is open at 45a17b3. |

## For a person before release, not covered by any criterion

Owner: Randy.

- **Screen readers.** Hearing real VoiceOver (macOS) and Narrator (Windows) speak Chatmon's announcements. M4A's
  criteria stop at the accessibility API, and the WSL runs drive Orca only as an AT-SPI client.
- **Hyprland and KDE.** The overlay and the unhosted ask box have only been tried on sway.
