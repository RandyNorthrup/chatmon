# M4A readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier reviews are readiness-review.txt through readiness-review-4.txt in [reports/m4a](..). Their receipts went
stale because the rules they were bound to changed. This review re-reads M4A's obligations against the brief and rules
as they are now. It is a requirements review, not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M4A-01 to M4A-11. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The rule for evidence from elsewhere settles the issue CI-linux
  raised. M4A's WSL receipts were recorded under a Linux profile, which closure flags. Runs on Linux, from CI or from WSL
  launched here, are now recorded under the plan's own profile, with the method saying where the run really happened.
- `pyproject.toml` at fb19cb9: M6A's stricter pytest settings and M6B's ruff and mypy settings, added since. No
  criterion depends on a laxer setting.

## Requirements and criteria

M4A-01 to M4A-11 map both ways to AC-01a through AC-11 (18 criteria), each with an owning task and an observable
result. Platform reach is explicit in each criterion's `given`: macOS for AC-01c, AC-03 and AC-06b, Qt 6.10 or later
for AC-04b, a Linux bus for the D-Bus criteria, and Windows for AC-09.

## Since the last review

- **CI-macos.** CI ran the macOS end-to-end tests that T-04 and T-09 were waiting for. Their red drills already ran on
  Windows against stand-ins for AppKit, and they ran again in this wave. Nothing else is outstanding for those tasks.
- **CI-linux.** CI ran the D-Bus and X11 tests. CI's locked PyQt6 6.11 skips the one test of AC-04b's Qt 6.10 signal
  (`test_qts_contrast_change_is_passed_on`). It runs in WSL with PyQt6 6.12, and its drill now mutates the
  `changed.connect(self.settings_changed)` line that replaced the old text.
- **CI-windows-comtypes.** The outcome is known: CI still skips the UI Automation client test, because comtypes isn't in
  `packaging/requirements-test.txt`. AC-09a doesn't ask for CI. It asks for the announcement to reach a UI Automation
  client, and the test proves that on this workstation, where comtypes is installed. Adding comtypes to the test locks
  is a follow-up for whoever owns the locks, not an M4A obligation.
- **AC-08-not-held** mutated text that changed in `a11y.py`. AC-08's other drills still apply.

## Findings

- Real VoiceOver and Narrator speech (a person hearing the announcement) is outside M4A's criteria, which stop at the
  post to the accessibility API. Hearing it is a release check for a person. The Outcome in ROADMAP.md lists it, with
  its owner.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
