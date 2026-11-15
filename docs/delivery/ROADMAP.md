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

## Rule amendments

| Date | Rule file | Old revision | New revision | Change | Why, and by whose authority | Work affected |
|---|---|---|---|---|---|---|
| 2026-11-14 | `docs/delivery/ROADMAP.md` | `5346385` and later labels (`4fdf790`, `78853bf`, `81af7c7`, `cac0047`) | `fb19cb9+wave4` | The three owner decisions above, *Evidence rules*, this table, and *Outcome* | The owner's decisions; the coordinator's wave-4 instructions to reconcile the plans with the CI runs and record the canonical bytes. Not to excuse any failure: every stale check was run again, or read from CI's logs. | Every plan's receipts, re-bound in wave 4 (the earlier ones kept as stale history) |
| 2026-11-14 | `pyproject.toml` | each plan's own label | `fb19cb9` | No edit in wave 4. The plans now name the content their receipts were checked against: M6A's pytest settings, M6B's ruff and mypy settings, the package data | Later merges, by their milestones' owners | Same as above |

## Outcome

Status at **fb19cb9**, after wave 4's reconciliation. CI run 43677128712 (every job green), Packages run 43675230966
(every build job green, release jobs skipped as designed) and PR #18's own checks on fb19cb9's tree (23 passed, the 5
release jobs skipped; [reports/wave4/ci/pr18-checks.txt](reports/wave4/ci/pr18-checks.txt)) answered most of the
pending operations. Every stale check was run again on this tree, or
read from those runs. Two other workers are changing code now (wayland: the overlay and `ci.yml`, with M3 reopened;
followups: packaging, the requirements and the mypy settings). Their merges make some of these receipts stale again,
and each plan's next action says what to re-run.

| Milestone | State | What's left, why, and who |
|---|---|---|
| M0 App core | checkpoint | M0-03.A3's "without copying the chats". `menus.chats_menu` reads the light listing today, but no test would notice it going back to whole chats: drill W4-M0-03-light-copies survived. A worker who may change code adds a menu-level test to `tests/test_app_smoke.py` (the coordinator names who); then the drill must go red. Everything else is verified, CI-posix included. |
| M1A Security, updates | checkpoint | AC-01-MACOS's red drill needs macOS (`ditto`, BSD `find`, `osascript`), and there is no Mac here or in the test lab. Randy on a Mac, or the coordinator with a throwaway drill branch on CI. CI-MACOS, CI-CONTAINER and MERGE-ISOLATION are resolved. |
| M1B Brains, stored data | closed | CI-MACOS, CI-LINUX and CI-WINDOWS were observed in CI. M7-WIRING was done by M7. |
| M2 Bubbles, ask box | closed | P-M2-ci was observed: every M2 test passed on every leg. |
| M3 Stage, overlay | not reconciled here | Reopened by the wayland worker, who owns its plan and reports. |
| M4A Platform awareness | closed | CI-macos and CI-linux were observed. AC-04b's Qt 6.12 test ran in WSL, because CI's PyQt6 6.11 skips it. CI-windows-comtypes: CI still skips the UI Automation client test, so comtypes needs adding to the test locks (a follow-up below). |
| M4B Hotkey, sound, toasts | checkpoint | Four red drills need a place to run. AC-00C, AC-01D and AC-02F need macOS: Randy on a Mac, or the coordinator through CI. AC-03E needs a Windows desktop with notifications on, which this PC's user has off: Randy turns them on for one run, approves a test PC's signed-in desktop, or the coordinator uses CI. All three CI operations are resolved. |
| M5 Reminders, offline, locale | closed | Its receipts were re-bound. |
| M6A CI and tooling | checkpoint | M6A-10.A1: two sentences in CONTRIBUTING.md (warnings "all but ResourceWarning", mypy's `ignore_errors` exemptions) are no longer true; the coordinator or the followups worker fixes them. P-RELEASE: the 0.10.0 tag, Randy or the coordinator. P-DEPENDABOT: Dependabot's first run once `.github/dependabot.yml` is on `main`, the coordinator. P-CI-FIRST, P-COVERAGE-FLOOR, P-PACKAGES-PR and P-MYPY-MERGES are resolved. |
| M6B Static analysis, logging | closed | Integration note 1's CI run happened, every job green. |
| M7 Integration | checkpoint | WAYLAND-HOSTING: `set_hosting(False)` with Orca on a real Wayland compositor (Hyprland or KDE). It's a person's check, with no compositor or screen reader here or in CI. Randy, before release. CI-ALL-PLATFORMS is resolved. |
| M8 Translation | closed | The Linux and macOS legs it named passed. |
| M9 Sounds (coordinator) | done | The owner accepted the cues as they are (2026-11-14). |
| Consolidation | the coordinator's | The version is 0.10.0, and the README and changelog are written (`d3f6a6e`). PR #18 (`improve/assessment-fixes` to `main`) is open. |

**Not covered by any criterion, for a person before release.** Hearing real VoiceOver (macOS) and Narrator (Windows)
speak Chatmon's announcements. M4A's criteria stop at the post to the accessibility API, and that post is tested.
Owner: Randy.

**Follow-ups outside `docs/delivery/`, for their owners.**

- CONTRIBUTING.md's two stale sentences (M6A-10.A1 above).
- Raise `fail_under` from 72 to about 84, now that the three OSes measure 86.2% (`pyproject.toml`, the followups
  worker).
- Add comtypes, for Windows, to the test locks, so CI runs the UI Automation client test that only this workstation
  runs today (`packaging/requirements-test.*`, the followups worker).
- A menu-level test that fails if the Chats menu goes back to reading whole chats (M0-03.A3 above).
