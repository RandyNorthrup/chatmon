## Reconciliation, wave 4 (2026-11-14)

This plan closed waiting for one thing, integration note 1: the feature branch's CI run on Linux under xvfb, in the
distribution containers and on macOS. That run has happened. Every receipt had also gone stale. The M6A and M8 plans it
takes as inputs changed, and hashes had been taken on a CRLF checkout while git stores LF. Wave 4 re-ran the checks on
**fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes (ROADMAP.md, *Canonical bytes*), after
M6A and M8 were re-bound. Two other workers were changing code at the same time. One of them, followups, is changing
the mypy settings. Their merges will make some of these receipts stale again.

**What CI answered.** CI run 43677128712 on fb19cb9, every job green. Each leg's result for this plan's tests is in
[reports/m6b/ci/observed.txt](reports/m6b/ci/observed.txt).

- `ruff check .` passed on the lint job ("All checks passed!").
- `mypy --platform` passed on the linux, win32 and darwin types jobs, with no override and no exemption.
- Every test passed with every warning an error on the Ubuntu legs under xvfb, on the macOS legs, and in the
  ubuntu:24.04, debian:trixie and fedora:44 containers on their own PyQt6.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped) and `packaging/extract_strings.py --check`. All 30 Windows drills and all 5 Linux drills (in WSL),
and all 16 gate drills (ruff's eleven families and the hub files, mypy on four modules), every one green, red and green
again. The requirements were reviewed again against the amended rules and the re-bound M6A and M8 plans
([wave4/readiness.md](reports/m6b/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M6B on fb19cb9.
