| 2026-11-14 | The repository's security settings are on: secret scanning, push protection, Dependabot alerts and Dependabot security updates. `main` is protected and requires the 18 CI checks: lint, types (linux, win32, darwin), the nine test legs, distro (ubuntu:24.04, debian:trixie, fedora:44), gnome and coverage. Observed in [reports/wave4/github-settings.txt](reports/wave4/github-settings.txt). |
| 2026-11-14 | The sound cues are accepted as they are (M9's files in `chatmon/sounds/`). |
| 2026-11-14 | The cap of five agents: at most five agents work on this delivery at once. |

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
| 2026-11-14 | `docs/delivery/ROADMAP.md` | `5346385` and later labels (`4fdf790`, `78853bf`, `81af7c7`, `cac0047`) | `fb19cb9+wave4` | The three owner decisions above, *Evidence rules*, this table, and *Outcome* | The owner's decisions; the coordinator's wave-4 instructions to reconcile the plans with the CI runs and record the canonical bytes. Not to excuse any failure: every check was run again. | Every plan's receipts, re-bound in wave 4 (the earlier ones kept as stale history) |
| 2026-11-14 | `pyproject.toml` | each plan's own label | `fb19cb9` | No edit in wave 4. The plans now name the content their receipts were checked against: M6A's pytest settings, M6B's ruff and mypy settings, the package data | Later merges, by their milestones' owners | Same as above |

## Outcome

Status at **fb19cb9**, after wave 4's reconciliation. CI run 43677128712 (every job green) and Packages run 43675230966
(every build job green, release jobs skipped as designed) answered most of the pending operations. Every stale check
was run again on this tree, or read from those runs. Two other workers are changing code now (wayland: the overlay and
`ci.yml`, with M3 reopened; followups: packaging, the requirements and the mypy settings). Their merges make some of
these receipts stale again, and each plan's next action says what to re-run.

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
