# Improvement roadmap, 2026-11-14

This roadmap covers every finding in [ASSESSMENT.md](ASSESSMENT.md) apart from distribution, which is deferred. Each
milestone is its own work unit with its own plan (`docs/delivery/<id>-*.md`) and reports
(`docs/delivery/reports/<id>/`). Task states live only in those plans; this file orders them and says who owns what.

The work happens on branch `improve/assessment-fixes`, which ends in one PR to `main`. There are no tags or releases;
the version becomes 0.10.0 in the final consolidation.

## Owner decisions

| Date | Decision |
|---|---|
| 2026-11-14 | Implement every finding and feature idea in the assessment. Distribution (macOS notarization, PyPI, AUR, winget) is assessed later. |
| 2026-11-14 | Git: feature branch, one commit per phase, push the branch so CI tests all three OSes, one PR at the end. |
| 2026-11-14 | Attached text: "what is best for the user." Coordinator's call: keep attached text with the chat so carrying on after a restart works, re-send it only to the brain it was given to, store it only on this computer (non-roaming on Windows), and write nothing when Keep chat history is off. The README is corrected to say so (M1B-17, M1A-11). |
| 2026-11-14 | Sounds play for alerts only by default: needs-you, reminders and focus done. Everything else is silent unless turned on. All sound is quiet during Do Not Disturb, Focus and full-screen. One switch turns all sound off. |
| 2026-11-14 | Sounds come from ElevenLabs Sound Effects (the owner's paid plan) and the owner's own synthesized sounds in `Documents\ContentLibrary\explainer-channel\sfx`. Making them is a flow in the flow skill. |
| 2026-11-14 | Translation: plumbing plus locale formats. Every UI string can be translated, times and dates follow the system locale, and offline phrases are per-language data with English always accepted. Only English ships. |
| 2026-11-14 | No new runtime dependencies (the project's own rule: its own Wayland client and Ed25519). OS facilities are reached through ctypes, QtDBus or Qt modules already shipped. Test-only additions (Hypothesis, pytest-timeout, coverage, mypy) are fine. |
| 2026-11-14 | The repository's security settings are on: secret scanning, push protection, Dependabot alerts and Dependabot security updates. `main` is protected and requires the 18 CI checks: lint, types (linux, win32, darwin), the nine test legs, distro (ubuntu:24.04, debian:trixie, fedora:44), gnome and coverage. Observed in [reports/wave4/github-settings.txt](reports/wave4/github-settings.txt). |
| 2026-11-14 | The sound cues are accepted as they are (M9's files in `chatmon/sounds/`). |
| 2026-11-14 | The cap of five agents: at most five agents work on this delivery at once. |
| 2026-11-15 | The `sway` job (a headless sway of the tests' own running `tests/test_sway.py` and `tests/test_wayland.py`) is one of `main`'s required checks, 19 in all. Observed in [reports/wave4b/github-settings.txt](reports/wave4b/github-settings.txt). |

## Waves

| Wave | Milestones | Runs |
|---|---|---|
| 1 | M0, M1A, M1B, M2, M3, M4A, M4B, M5, M6A, M9 | In parallel. Each worker has its own worktree and owns the files listed below. |
| 2 | M7 | After every wave-1 branch is merged. It wires the APIs wave 1 added into `app.py` and `settingswin.py`. |
| 3 | M8, then M6B | One at a time, because both touch every module. |
| 4 | Consolidation | README, `changelog.md` (0.10.0), the version, the full test run, push, PR. Then every plan reconciled with the PR's CI runs and its stale receipts re-run (*Evidence rules* and *Outcome* below). |

## File ownership in wave 1

A worker changes only the files its milestone owns, plus new files it creates and its own tests. Any change that
belongs elsewhere becomes an integration note in its plan, for M7 (or the owner of that file) to make.

| Milestone | Owns |
|---|---|
| M0 Architecture and app core | `chatmon/app.py`, `chatmon/cli.py`, new `chatmon/messages.py`, `chatmon/asking.py`, `chatmon/menus.py`, `chatmon/commands.py`; tests `tests/test_messages.py`, `tests/test_cli.py`, `tests/test_app_smoke.py` |
| M1A Security, updates, IPC, packaging | `chatmon/updates.py`, `chatmon/wintrust.py`, `chatmon/events.py`, `chatmon/winpipe.py`, `chatmon/paths.py`, `chatmon/agents.py`, `chatmon/attachments.py`, `chatmon/ed25519.py`, `packaging/linux/**` (including `nfpm.yaml`), `packaging/macos/**`, `packaging/windows/*.iss`, `packaging/build.py`, `packaging/chatmon.spec`, `chatmon/integrations/**`; tests for these. M6A-14 (release notes pin) moves here, since it is in `build.py`. |
| M1B Brains and stored data | `chatmon/brains.py`, `chatmon/chats.py`, `chatmon/memory.py`, `chatmon/settings.py`, new `chatmon/keychain.py`, new `chatmon/backup.py`; tests for these |
| M2 Bubbles and ask box | `chatmon/bubble.py`, `chatmon/bubbleart.py`, `chatmon/styles.py`, new `chatmon/highlight.py`; tests for these |
| M3 Stage, sprites, overlay | `chatmon/penguin.py`, `chatmon/sprites.py`, `chatmon/behavior.py`, `chatmon/stagemenu.py`, `chatmon/clickthrough.py`, `chatmon/layer.py`, `chatmon/wayland.py`, `chatmon/xkb.py`, `chatmon/companions.py`; tests for these |
| M4A Platform awareness | `chatmon/presence.py`, `chatmon/a11y.py`, `chatmon/macnative.py`, `chatmon/linuxsession.py`, `chatmon/sysnotify.py`, `chatmon/heads_up.py`, `chatmon/portal.py`, `chatmon/winlock.py`; tests for these |
| M4B Hotkey, sound, toasts | new `chatmon/hotkey.py`, `chatmon/sound.py`, `chatmon/wintoast.py`, `chatmon/winfocus.py`; tests for these. The sound files themselves are M9's. |
| M5 Reminders, offline, locale | `chatmon/reminders.py`, `chatmon/offline.py`, `chatmon/context.py`, new `chatmon/phrases/` (data) and `chatmon/localefmt.py`; tests for these |
| M6A CI and tooling | `.github/**`, `pyproject.toml` (`[tool.*]` sections, `[project.optional-dependencies]` and `[project.scripts]`; package-data globs are coordinated, see below), `packaging/requirements*.txt`, root `penguin-companion`, `SECURITY.md`, `CONTRIBUTING.md`, `tests/conftest.py`, `tests/test_windows.py`, new `tests/test_package_data.py` |
| M9 Sounds (coordinator) | `chatmon/sounds/**`, `art/sounds/**`, the flow skill |

**Shared files nobody edits in wave 1:** `README.md`, `chatmon/changelog.md`, `chatmon/__init__.py` (the version) and
`chatmon/settingswin.py`. Each plan keeps a **Changelog notes** section and a **README notes** section, which the
consolidation turns into the real text.

**`pyproject.toml` package data:** new data folders (`chatmon/sounds/*.wav`, `chatmon/phrases/*.json`) are added to
`[tool.setuptools.package-data]` by M6A. M5 and M9 name their globs in their plans' integration notes.

## Contracts between milestones

- **M0 queue and M5 reminders.** M5 gives the reminder book `due(now)`, which returns fired, unacknowledged reminders
  without removing them, plus `acknowledge(id)`, `snooze(id, until)` and `update(id, text=None, when=None)`. M0's
  queue treats a reminder as priority "reminder" and never drops it. M7 joins them.
- **M2 and M7.** The ask box emits `stop_requested`, `copy_requested(str)`, `more_requested` and
  `expand_changed(bool)`, and takes `set_busy(label, started_at)`, `append_partial(text)` and `set_text_scale(float)`.
  Speech bubbles take `set_hovered(bool)` and a `timeout_policy`.
- **M3 and M7.** The stage takes `set_badge(...)`, `set_reduced_motion(bool)`, `set_drawing(bool)`, `set_covered(...)`
  and `follow_pointer_screen(bool)`, plus an unhosted ask-box mode. StageMenu takes keys through
  `StageMenu.key(event) -> bool`, which M3 itself routes from `Stage.key`.
- **M1B and M7.** `Asker` emits `partial(str)` while streaming. Keys are reached through `keychain.get/set/delete`,
  and brains have a `test()` call.
- **M4B and M7.** `hotkey.register(sequence, callback) -> error | None`, `sound.play(cue)` with
  `sound.configure(enabled, volume, cues)`, and `wintoast.show(title, text, buttons, scenario)`.

Each worker writes the APIs it actually delivered into its plan's **Integration notes**, which M7 reads.

## Rules for every worker

1. Load the `high-quality-projects-skill:feature_delivery` skill and follow it, with
   `docs/delivery/ASSESSMENT.md` as the brief.
   - The plan is `docs/delivery/<id>-<slug>.md`, with one `quality-ledger` block.
   - Reports, logs and context go in `docs/delivery/reports/<id>/`.
   - Rule references are `pyproject.toml` (ruff, pytest config) and this roadmap.
2. Read the code before changing it. Re-check a finding that has no ✓. A finding that turns out to be wrong is
   recorded as such in the plan, not "fixed".
3. Write tests in the project's existing style: real Qt objects under `QT_QPA_PLATFORM=offscreen`, the `qapp`
   fixture, and no mocks that bypass the behavior under test. Platform-specific code gets tests that run on its
   platform in CI, and skip with a reason elsewhere.
4. Red drills go through `python tests/drills/run.py docs/delivery/reports/<id>/drill-spec.json --log
   docs/delivery/reports/<id>/drills.log`. The drills run in a temporary copy, so the tree is never mutated.
5. Gates before every commit:
   - `python -m pytest -q -p no:cacheprovider` (the whole suite) and `ruff check .` must pass.
   - Report the pass and skip counts.
6. Commit to your worktree branch in logical steps, in the repository's message style: a plain sentence saying what
   changed for the user, then a body if needed. End each message with:

   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   ```

   Never push, merge, tag or rebase shared branches; the coordinator merges.
7. Keep the project's voice:
   - Comments and user-facing strings are plain English sentences that explain why.
   - No new runtime dependencies.
   - Keep the README's privacy promises true.
8. Finish with a closure-validated plan, or a checkpoint naming the real blockers, and report back:
   - the branch name;
   - what was delivered, by assessment ID;
   - test and drill results;
   - integration notes, changelog notes and README notes.

## Evidence rules (wave 4)

These two rules came from wave 4's reconciliation. They apply to every plan's receipts.

**Canonical bytes.** A receipt binds the repository's bytes: what git stores, and what an LF checkout or CI's Linux
and macOS runners check out. Every text file here is stored with LF. A Windows checkout with `core.autocrlf=true` writes
CRLF, so a hash taken there never matches git's bytes. Several wave-1 to wave-3 receipts were hashed that way, and
others were hashed on LF, so a plan could only validate on the checkout it was written on. From wave 4 on:

- **Validate and bind on a checkout that writes git's bytes.** In a worktree:

  ```
  git config extensions.worktreeConfig true
  git config --worktree core.autocrlf false
  ```

  Then check every tracked file out again: `git checkout-index -f` doesn't rewrite files git thinks are clean, so
  remove them and run `git checkout -- .`. `git ls-files --eol` then shows `i/lf w/lf` for every text file. A checkout
  with `core.autocrlf=true`, the Git for Windows default, can't validate these plans.
- **Keep artifacts byte for byte as their tool wrote them**: CRLF from Windows' Python and pytest, LF from `gh` and
  WSL. With `core.autocrlf=false`, git stores them as written. Git leaves a file that already holds CRLF alone on any
  checkout, so those artifacts read the same everywhere. An LF-only artifact still needs an LF checkout, like the
  sources.
- **Drill texts.** Drill specs written on a CRLF checkout carry CRLF inside their multi-line `find` texts. Their
  wave-4 copies (`reports/<id>/wave4/drill-spec*.json`, made by
  [reports/wave4/lfspec.py](reports/wave4/lfspec.py)) turn CRLF into LF and change nothing else. A drill whose text no
  longer occurs is left out of the copy and named in `drills-left-out.txt`.

**Evidence from elsewhere.** A plan has one verification profile, this Windows workstation's. Checks that run
somewhere else are recorded under that profile, with the method saying where they really ran:

- **CI.** The receipt's command is the `gh run view RUN --job JOB --log` that fetched the log here. Its artifact is
  that log. Each test's result is read by [reports/wave4/cilog.py](reports/wave4/cilog.py), which maps pytest's
  progress characters onto the collection of the same source and checks them against the run's own counts and skip
  lines.
- **WSL.** The command is the `wsl.exe -d archlinux -- ...` launched from here. Drills go through
  [reports/wave4/wsl_drills.py](reports/wave4/wsl_drills.py), which hands each drill to `tests/drills/run.py`'s own
  step.
- **Versions.** The run's own platform and versions are in its log. Earlier receipts recorded under a Linux or "CI"
  profile were flagged by closure for exactly that reason (M4A, M4B).
- **Round two** (2026-11-15, bf9d8ac) works the same way, in `reports/<id>/wave4b/` and
  [reports/wave4b/](reports/wave4b/): CI run 43701523023 and Packages run 43701523037, both PR #18's own runs, whose
  test merge has bf9d8ac's tree, read with [reports/wave4/observe_bf9d8ac.py](reports/wave4/observe_bf9d8ac.py).
  The scripts it binds with are `reports/wave4/mkbind2.py` and `bind.py`.
- **Round three** (2026-11-15, 3586a0d, wave4/crash merged) works the same way, in `reports/<id>/wave4c/` and
  [reports/wave4c/](reports/wave4c/): CI run 43729628408 and Packages run 43729628343, PR #18's own runs. Their test
  merge `5545f5a` has 3586a0d's tree ([reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)). They are
  read with [reports/wave4/observe_3586a0d.py](reports/wave4/observe_3586a0d.py), and the plans are bound with
  `reports/wave4/mkbind3.py` and `bind.py`. This file is a rule of every plan, so amending its Outcome stales every
  receipt of every plan, not only the receipts bound to the files a merge changed. So round three ran every plan's
  checks again, or read them from those runs. M10's are among them, bound here for the first time on git's bytes.

## Rule amendments

| Date | Rule file | Old revision | New revision | Change | Why, and by whose authority | Work affected |
|---|---|---|---|---|---|---|
| 2026-11-14 | `docs/delivery/ROADMAP.md` | `5346385` and later labels (`4fdf790`, `78853bf`, `81af7c7`, `cac0047`) | `fb19cb9+wave4` | The three owner decisions above, *Evidence rules*, this table, and *Outcome* | The owner's decisions; the coordinator's wave-4 instructions to reconcile the plans with the CI runs and record the canonical bytes. Not to excuse any failure: every stale check was run again, or read from CI's logs. | Every plan's receipts, re-bound in wave 4 (the earlier ones kept as stale history) |
| 2026-11-14 | `pyproject.toml` | each plan's own label | `fb19cb9` | No edit in wave 4. The plans now name the content their receipts were checked against: M6A's pytest settings, M6B's ruff and mypy settings, the package data | Later merges, by their milestones' owners | Same as above |
| 2026-11-15 | `docs/delivery/ROADMAP.md` | `fb19cb9+wave4`, M3's `964510f`, M4A's `5c6093e` | `bf9d8ac+wave4b` | The sway decision above, round two's note in *Evidence rules*, this row, and *Outcome* rewritten for bf9d8ac | The coordinator's round-two instructions (re-bind and close against bf9d8ac). Not to excuse any failure: every stale check was run again, or read from CI's logs of bf9d8ac. | All twelve plans but M10's (the followups worker's), re-bound in round two; earlier receipts kept as stale history |
| 2026-11-15 | `pyproject.toml` | `fb19cb9`, `964510f`, `5c6093e` | `bf9d8ac` | No edit by this work. Since fb19cb9: `fail_under` 72 to 84, comtypes in the test extra and dev pins, ruff's rule exemptions for `docs/delivery/reports/wave4/**` | The followups worker and the coordinator | Same as above |
| 2026-11-15 | `docs/delivery/ROADMAP.md` | `bf9d8ac+wave4b`, and M10's `fb19cb9` | `3586a0d+wave4c` | Round three's note in *Evidence rules*, these two rows, and *Outcome* rewritten for 3586a0d. No owner decision changed. | The coordinator's round-three instructions (refresh the receipts that bind wave4/crash's files, re-bind and close M10, use PR #18's CI on 3586a0d, Outcome at 3586a0d). Not to excuse any failure: every check was run again on 3586a0d, or read from CI's logs of it. | All thirteen plans, M10's among them, re-bound in round three; earlier receipts kept as stale history |
| 2026-11-15 | `pyproject.toml` | `bf9d8ac`, and M10's `wave4/followups` | `3586a0d` | No edit since bf9d8ac. M10's label stood for its own change (comtypes in the test extra and dev pins), before `fail_under` 72 to 84 and ruff's exemptions for `docs/delivery/reports/wave4/**` | The followups worker and the coordinator | Same as above |

## Outcome

Status at **3586a0d**, after round three of wave 4's reconciliation (2026-11-15). 3586a0d is `improve/assessment-fixes`
with wave4/crash merged. wave4/crash frees quit test Companions between tests (CI's fedora:44 crash), and makes sure
nothing a quit Chatmon had waiting runs. PR #18's own runs on 3586a0d were all green. CI run 43729628408 passed its
19 jobs. Packages run 43729628343 passed its five build jobs and skipped the five release jobs, as designed for a run
that isn't a tag. Their test merge has 3586a0d's tree. Every check of the thirteen plans was run again on 3586a0d or
read from those runs. wave4/crash's own seven drills (CRASH-01 to CRASH-07) went green, red and green again here too
([reports/wave4c/crash/](reports/wave4c/crash/)). Round two's Outcome, at bf9d8ac, is in this file's history
(`git show 23035ac:docs/delivery/ROADMAP.md`).

| Milestone | State | What's left, why, and who |
|---|---|---|
| M0 App core | closed | Re-bound at 3586a0d. |
| M1A Security, updates | checkpoint | AC-01-MACOS's red drill needs macOS (`ditto`, BSD `find`, `osascript`). Owner: Randy on a Mac, or the coordinator with a throwaway drill branch on CI. Everything else is verified at 3586a0d. |
| M1B Brains, stored data | closed | Re-bound at 3586a0d. |
| M2 Bubbles, ask box | closed | Re-bound at 3586a0d. |
| M3 Stage, overlay | closed | Re-bound at 3586a0d: CI's `sway` job passed again (49 passed, and 3 skipped because CI has no Orca or wlr-protocols), and the real-Orca tests ran in WSL. The whole suite in WSL fails one test that is none of M3's (*Found in round three*), so M3's own test files ran on their own there instead and passed. |
| M4A Platform awareness | closed | Re-bound at 3586a0d: T-04 and T-09's macOS tests passed again on CI's three macOS legs. |
| M4B Hotkey, sound, toasts | checkpoint | Four red drills need somewhere to run. AC-00C, AC-01D and AC-02F need macOS: Randy on a Mac, or the coordinator through CI. AC-03E needs a Windows desktop with notifications on: Randy turns them on for one run, approves a test PC's signed-in desktop, or the coordinator uses CI. |
| M5 Reminders, offline, locale | closed | Re-bound at 3586a0d. |
| M6A CI and tooling | checkpoint | **M6A-10.A1 fails at 3586a0d** on one CONTRIBUTING.md sentence, "It also passes with the next PyQt6's stubs (6.12.1)": see *Found in round three* below. T7 is blocked on it. Owner: the coordinator. Two outcomes remain besides, both pending operations. P-RELEASE: the 0.10.0 tag (none yet; the newest is v0.9.2), Randy or the coordinator. P-DEPENDABOT: Dependabot's first run once `.github/dependabot.yml` is on `main`, the coordinator. |
| M6B Static analysis, logging | checkpoint | **M6B-02.A1's 6.12 half fails at 3586a0d** (*Found in round three*). T4-mypy is blocked on it. Owner: the coordinator. The 6.11 half, CI's `types` jobs, and every other criterion pass. |
| M7 Integration | closed | Re-bound at 3586a0d. The crash fix moved one drill's line (the palette's one-off wait), so W4-M7-11-palette-ignored-v2 takes it out where it is now, and its test fails. WAYLAND-HOSTING is answered on sway 1.12 with the real Orca 51.1 (WSL), and on sway 1.9 without Orca (CI). **Hyprland and KDE themselves were not tested.** |
| M8 Translation | closed | Re-bound at 3586a0d. The crash fix adds no string anyone sees: the template is current. |
| M9 Sounds (coordinator) | done | The owner accepted the cues as they are (2026-11-14). |
| M10 Follow-ups | checkpoint | Re-bound at 3586a0d, on git's bytes, for the first time since its own worker. Integration note 1 is in the tree (the wayland worker's `964510f`), so `layer.py` and `penguin.py` pass with PyQt6 6.12.1's stubs. But **M10-03.A1's 6.12.1 half fails** (*Found in round three*), and four of its gate drills couldn't start. T3-qt612-types is blocked on it. Owner: the coordinator. Everything else passes. One pending operation, not a criterion: from 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check against the next stubs (P-CI-NEXT-STUBS), the coordinator. That check would catch such a line in CI. The owner: the upstream report on PyQt6's stubs (note 4), which needs his mailing-list account. |
| Consolidation | the coordinator's | Version 0.10.0, README and changelog. PR #18 (`improve/assessment-fixes` to `main`) is open at 3586a0d. |

**Found in round three: one line of the crash fix fails mypy with PyQt6 6.12.1's stubs.** The line is
`widget.removeEventFilter(self)` in `Companion._stop_for_good`, at `chatmon/app.py:3173`. On linux, win32 and darwin,
here and in WSL: `Argument 1 to "removeEventFilter" of "QObject" has incompatible type "Companion"; expected "AskBox"
[arg-type]`. 6.12.1's stubs type the filter as `Self`, the watched object. That is the stub bug CONTRIBUTING.md's
third workaround covers (`# type: ignore[arg-type]` with the reason), and the line doesn't have it. CI is green
because its `types` jobs lock 6.11's stubs, which pass. Three criteria fail on it: M6B-02.A1's 6.12 half, M10-03.A1's
6.12.1 half, and M6A-10.A1's CONTRIBUTING.md sentence that mypy also passes with them. This reconciliation changes
no product code. **Owner: the coordinator**, with the one-line ignore. Then M10's `mypy_runs.py` with the 6.12.1 venv,
M10's `wave4c/gate_drills.py` and M6A's docs review run again, and M6A, M6B and M10 can be re-bound.

**Found in round three: the crash fix's own test fails on a Linux with UPower.** In WSL Arch the whole suite gives
1 failed, 1315 passed, 121 skipped ([reports/wave4c/suite-linux.log](reports/wave4c/suite-linux.log)). The failure is
`tests/test_app_smoke.py::test_a_quit_companion_runs_nothing_it_had_waiting`: after quit, `Companion._power_saving`
ran. `linuxsession.PowerProfile` asks the system bus for UPower's `OnBattery`, and its answer comes back after quit.
`Companion._stop_for_good` stops the Companion's own waits, timers and threads, but not that watcher. It fails five
runs in five with UPower on WSL's system bus, and passes with no system bus
([reports/wave4c/crash-test-wsl.log](reports/wave4c/crash-test-wsl.log)). CI's runners have no such bus, so CI passes
it, as does Windows. A Linux contributor whose system bus has UPower would see the suite fail the same way. No plan's
criterion is about it; M3's WSL receipt now runs M3's own test files instead of the whole suite. **Owner: the
coordinator** (wave4/crash's guarantee): the power watcher, and any other system-bus watcher that calls back into the
Companion, stopped or ignored once it has quit.

**For a person before release, not covered by any criterion.**

- Hearing real VoiceOver (macOS) and Narrator (Windows) speak Chatmon's announcements. M4A's criteria stop at the
  accessibility API, and the WSL runs drive Orca only as an AT-SPI client.
- Hyprland and KDE: the overlay and the unhosted ask box have only been tried on sway.

Owner: Randy.

**Round one's follow-ups, all done:**

- CONTRIBUTING.md's two sentences.
- `fail_under` raised from 72 to 84.
- comtypes added to the test lock.
- The M0 menu test.
