# M10 readiness, round three at 3586a0d (wave 4, 2026-11-15)

The followups worker's review is [../readiness.md](../readiness.md), at fb19cb9, with its decisions D1 to D19. Its
receipt went stale for three reasons. It was hashed on a CRLF checkout, against ROADMAP's *Canonical bytes*. ROADMAP.md
(a rule) was amended in rounds two and three. And the a11y, wayland, sway and crash merges changed files it was bound
to. This review re-reads the plan's obligations against the brief and rules at 3586a0d. It is a requirements review,
not proof that the code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): unchanged since fb19cb9.
- [ROADMAP.md](../../../ROADMAP.md), amended in rounds two and three: the evidence rules (canonical bytes, evidence
  from elsewhere), the sway job among `main`'s required checks, and the Outcome at 3586a0d. None of them adds, removes
  or loosens a criterion of this plan.
- `pyproject.toml`: the plan's own changes (comtypes in the test extra and the dev pins), then `fail_under` 72 to 84
  and ruff's exemptions for `docs/delivery/reports/wave4/**`, neither about this plan. Unchanged since bf9d8ac.
- The plans this one takes as inputs (M4A, M6A, M6B, M8): re-bound in rounds two and three. Nothing in them asks this
  plan for more.

## This plan

M10-01 to M10-03 still map both ways to their seven criteria, each owned by one of the three tasks.

- **M10-01 (comtypes).** `packaging/requirements-test.in`, both locks and the extras are unchanged since the plan's
  commits. CI's three Windows test legs at 3586a0d install the test lock with `--require-hashes`, so the UI Automation
  end-to-end test now runs there, which is what M4A's note asked for. M10-01.A2 asks for the same in a fresh venv
  here, and that check is run again.
- **M10-02 (Qt's own translations).** `chatmon/i18n.py`, `packaging/build.py` and `packaging/chatmon.spec` are
  unchanged since the plan's commits. The frozen-app runs ([frozen-nuitka.log](../frozen-nuitka.log),
  [frozen-pyinstaller.log](../frozen-pyinstaller.log)) are observations, not receipts, and stay as they were.
- **M10-03 (PyQt6 6.12.1's stubs).** Integration note 1 is done. The wayland worker's `964510f` made the listed
  changes to `layer.py` and `penguin.py` (`wayland-files-qt6121.diff` applies in reverse on 3586a0d). So M10-03.A1's
  "and on those too once their listed changes are applied in a copy" is now true of the tree itself. Round three runs
  mypy with 6.12.1's stubs on the tree, where the plan ran it on a patched copy. The gate drills' copy no longer
  needs the patch either. `wave4c/gate_drills.py` checks that and applies it only if it still applies. T3 also owns
  `chatmon/app.py` and `chatmon/brains.py`, which the crash fix changed. Its new code declares no signal and takes no
  parent. But it passes the Companion to `removeEventFilter`, an argument 6.12.1's stubs type as `Self`, without the
  plan's workaround. The receipts show what that does (see the plan's round-three section). The requirement is
  clear about it: no module exempted, every stub bug fixed precisely.
- **M10-03.A3 (the how-to).** CONTRIBUTING.md's "Lint and types" section is unchanged since the plan's `d15d7a9`.
  The file's two later edits are to other sections: testing's `ResourceWarning` sentence and translation's Qt
  packages. Its "It also passes with the next PyQt6's stubs" was true of the merged branch only after note 1. The
  how-to is reviewed again and replayed in WSL on the tree as it is.

What is left is outside the criteria. M10-03 asks for a CI entry "only if it can be hash-locked like the rest", and
that can't happen until 6.12.1 is two weeks old.

- **Integration note 2, the CI check against the next stubs.** For the coordinator, from 2026-11-28. Recorded as a
  pending operation, not as passing.
- **Note 3, Dependabot's PyQt6 6.12.0.** Done: `.github/dependabot.yml` ignores 6.12.0 (M6A, round two).
- **Note 4, the upstream report.** The owner's to send, with his PyQt mailing-list account.
- **Note 5, `nfpm.yaml`'s recommends.** For when a language ships; CONTRIBUTING.md says so now.
- **Note 7, the CRLF hashes.** Answered by binding on git's bytes.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
