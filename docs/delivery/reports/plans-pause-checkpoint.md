> **Resumed 2026-11-15 at 00:20 PST, and finished.** The remaining WSL checks passed: M4A's 10 Linux drills and its Qt 6.12
> drill and run, M4B's 7, M6B's 5, and M6A's distro drill. ROADMAP.md gained its evidence rules and Outcome, and all 11
> plans were bound in the order below. Each plan's state is in ROADMAP.md's *Outcome*, and its validation in
> `reports/<id>/wave4/validate-*.txt`. This note is kept as the record of the pause.

# Wave 4 plans reconciliation: paused 2026-11-14 (about 22:15 PST, 06:15Z)

The pause was the owner's request. This file is a pause note, not a delivery plan, and it is not bound by any receipt.

- **Branch:** `wave4/plans`, worktree `C:\Users\Randy\Coding\chatmon-wt\plans`, from `improve/assessment-fixes` at
  `fb19cb9`. HEAD is the "WIP (paused)" commit that adds this file, on top of `fb19cb9`.
- **Nothing is running.** No pytest, drill or validator process is left on Windows or in WSL. The WSL batch was stopped
  mid-way through M4A's Linux drills, and its temporary copy was removed. No `*.lock` directory is left under
  `docs/delivery/`.
- **Worktree settings, kept:** `extensions.worktreeConfig=true` in the shared `.git/config`, and
  `core.autocrlf=false` in this worktree's `config.worktree`. Every tracked file was checked out again with git's LF
  bytes (`git ls-files --eol`: `i/lf w/lf`). Keep both settings. The receipts are bound to these bytes.

## State of the 11 plans

**No plan file has been changed yet.** Not one is closed or re-bound in this wave so far. Every plan's ledger, and
ROADMAP.md, is byte for byte as at `fb19cb9`. What exists is the evidence and the per-plan bindings input, all in
`docs/delivery/reports/`:

| Done (artifacts in the WIP commit) | Where |
|---|---|
| Whole suite on Windows at fb19cb9: 1241 passed, 148 skipped, exit 0 | `reports/wave4/suite-windows.log` |
| CI run 43677128712 (18 jobs) and Packages run 43675230966 (5 build jobs): job lists and every log | `reports/wave4/ci/` |
| The collection of fb19cb9, and `cilog.py` and `observe.py` (each test's result per CI leg) | `reports/wave4/` |
| Observed tool context, GitHub settings, `extract_strings.py --check` (exit 0) | `reports/wave4/context-observed.log`, `github-settings.txt`, `extract-strings-check.log` |
| Every applicable Windows drill, 357 of 357 green-red-green (LF copies of each spec, left-out drills listed) | `reports/<id>/wave4/drill-spec*.json`, `drills*.log`, `drills*-results.json`, `drills-left-out.txt` |
| New drills for criteria whose old drill text has gone: M0 (9 green, 2 survived, see below), M1B (2), M5 (1), M7 (2) | `reports/<id>/wave4/drill-spec-new*.json`, `drills-new*` |
| M6A: 10 gate drills, the reproducible-wheel check, the Windows Update opt-in, the Dependabot schema, CI's coverage combined (86.2%) | `reports/m6a/wave4/` |
| M6B: 16 gate drills | `reports/m6b/wave4/gate-drills*` |
| Linux drills in WSL: M0 (2), M1A (8), M1B (6), all green-red-green | `reports/{m0,m1a,m1b}/wave4/drills-linux*` |
| Readiness re-reviews, reconciliation sections, per-plan `extra.json` and `context.json`, all 11 plans | `reports/<id>/wave4/` |
| Draft ROADMAP additions (owner decisions, evidence rules, rule amendments, Outcome) | `reports/wave4/resume/roadmap-additions.draft.md` |

Findings so far, already written into the sections and extras:

- **M0-03.A3.** No test notices the Chats menu reading whole chats: drill W4-M0-03-light-copies survived.
  T-M0-03-light stays implemented.
- **W4-M0-05-unknown-id-kept** survived because the drill picked the wrong line. It is replaced by two drills that
  went red.
- **M6A-10.A1.** CONTRIBUTING.md has two stale sentences (ResourceWarning, mypy exemptions). The re-review fails.
- **M1A AC-01-MACOS, and M4B AC-00C, AC-01D and AC-02F,** need macOS for their red drills. M4B AC-03E needs a Windows
  desktop with notifications on.
- **M7 WAYLAND-HOSTING** needs a person with Orca on Hyprland or KDE.

## Not yet run (WSL; restart from here)

M4A's 10 Linux drills, M4B's 6 + 1 WSL drills, M6B's 5 Linux drills, M4A's Qt 6.12 drill and `test_presence.py` run
(with `/var/tmp/m4a-venv`), and M6A's distro drill (podman, debian:trixie, 3 container runs). The venv
`/var/tmp/plans-venv` (PyQt6 6.11.0, from `packaging/requirements-test.txt`) is ready in WSL.

## The exact next safe steps

1. In WSL:
   `bash /mnt/c/Users/Randy/Coding/chatmon-wt/plans/docs/delivery/reports/wave4/resume/run-wsl-batch.sh`.
   It skips the three specs already done and writes `reports/wave4/resume/wsl-progress.txt`. Check every summary for
   PASS, and fix any section or extra whose claim a result contradicts.
2. Put the draft additions into `docs/delivery/ROADMAP.md`: three owner-decision rows, *Evidence rules (wave 4)*,
   *Rule amendments*, *Outcome*. Adjust the Outcome to the WSL results. ROADMAP.md is a rule in every plan, so it must
   be final before any receipt is bound. Then commit ROADMAP.md and `reports/wave4/` ("wave 4's evidence rules ...").
3. Bind each plan in this order (M8 takes M0, M5 and M7 as inputs, and M6B takes M6A and M8):
   M0, M1A, M1B, M2, M4A, M4B, M5, M6A, M7, then M8, then M6B. For each one, run
   `bash docs/delivery/reports/wave4/resume/apply-plan.sh <id> <slug>` from the worktree. It runs `mkbind.py`, then
   `bind.py --apply` (update-delivery.py with the observed digest), then resume and closure validation into
   `reports/<id>/wave4/validate-*.txt`. Commit each plan on its own. Dry runs of M2, M5 and M7 passed (M7 failing
   only on WAYLAND-HOSTING), but they ran against the old ROADMAP and must be redone after step 2.
4. Delete `build/wave4-coverage/` (ignored; it was CI's combined coverage data for the floor drill) and
   `reports/wave4/resume/` once the plans are bound, then report.
