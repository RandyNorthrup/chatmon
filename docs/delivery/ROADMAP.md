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

## Waves

| Wave | Milestones | Runs |
|---|---|---|
| 1 | M0, M1A, M1B, M2, M3, M4A, M4B, M5, M6A, M9 | In parallel. Each worker has its own worktree and owns the files listed below. |
| 2 | M7 | After every wave-1 branch is merged. It wires the APIs wave 1 added into `app.py` and `settingswin.py`. |
| 3 | M8, then M6B | One at a time, because both touch every module. |
| 4 | Consolidation | README, `changelog.md` (0.10.0), the version, the full test run, push, PR. |

## File ownership in wave 1

A worker changes only the files its milestone owns, plus new files it creates and its own tests. Any change that
belongs elsewhere becomes an integration note in its plan, for M7 (or the owner of that file) to make.

| Milestone | Owns |
|---|---|
| M0 Architecture and app core | `chatmon/app.py`, `chatmon/cli.py`, new `chatmon/messages.py`, `chatmon/asking.py`, `chatmon/menus.py`, `chatmon/commands.py`; tests `tests/test_messages.py`, `tests/test_cli.py`, `tests/test_app_smoke.py` |
| M1A Security, updates, IPC, packaging | `chatmon/updates.py`, `chatmon/wintrust.py`, `chatmon/events.py`, `chatmon/winpipe.py`, `chatmon/paths.py`, `chatmon/agents.py`, `chatmon/attachments.py`, `chatmon/ed25519.py`, `packaging/linux/**` (except `nfpm.yaml` dependency lines owned by M6A), `packaging/macos/**`, `packaging/windows/*.iss`, `chatmon/integrations/**`; tests for these |
| M1B Brains and stored data | `chatmon/brains.py`, `chatmon/chats.py`, `chatmon/memory.py`, `chatmon/settings.py`, new `chatmon/keychain.py`, new `chatmon/backup.py`; tests for these |
| M2 Bubbles and ask box | `chatmon/bubble.py`, `chatmon/bubbleart.py`, `chatmon/styles.py`, new `chatmon/highlight.py`; tests for these |
| M3 Stage, sprites, overlay | `chatmon/penguin.py`, `chatmon/sprites.py`, `chatmon/behavior.py`, `chatmon/stagemenu.py`, `chatmon/clickthrough.py`, `chatmon/layer.py`, `chatmon/wayland.py`, `chatmon/xkb.py`, `chatmon/companions.py`; tests for these |
| M4A Platform awareness | `chatmon/presence.py`, `chatmon/a11y.py`, `chatmon/macnative.py`, `chatmon/linuxsession.py`, `chatmon/sysnotify.py`, `chatmon/heads_up.py`, `chatmon/portal.py`, `chatmon/winlock.py`; tests for these |
| M4B Hotkey, sound, toasts | new `chatmon/hotkey.py`, `chatmon/sound.py`, `chatmon/wintoast.py`, `chatmon/winfocus.py`; tests for these. The sound files themselves are M9's. |
| M5 Reminders, offline, locale | `chatmon/reminders.py`, `chatmon/offline.py`, `chatmon/context.py`, new `chatmon/phrases/` (data) and `chatmon/localefmt.py`; tests for these |
| M6A CI and tooling | `.github/**`, `pyproject.toml` (`[tool.*]` sections, `[project.optional-dependencies]` and `[project.scripts]`; package-data globs are coordinated, see below), `packaging/requirements*.txt`, `packaging/build.py`, `packaging/chatmon.spec`, `packaging/linux/nfpm.yaml`, root `penguin-companion`, `SECURITY.md`, `CONTRIBUTING.md`, `tests/conftest.py`, `tests/test_windows.py`, new `tests/test_package_data.py` |
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
4. Red drills go through `python tests/drills/run.py docs/delivery/reports/<id>/drills.json --log
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
