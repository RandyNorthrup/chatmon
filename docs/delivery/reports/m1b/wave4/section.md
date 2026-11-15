## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI runs this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered** (run 43677128712 on fb19cb9, every job green; each leg's result for this plan's tests is in
[reports/m1b/ci/observed.txt](reports/m1b/ci/observed.txt)):

- **CI-MACOS.** `test_macos_keychain_keeps_replaces_and_forgets_a_key` and
  `test_a_socket_of_yours_is_yours_and_a_closed_port_nobodys` passed on all three macOS legs.
- **CI-LINUX.** The three Secret Service tests passed on all three Ubuntu legs, not skipped, because `ci.yml` installs
  Ubuntu's `dbus`. So did the Linux port-owner tests and the file and folder modes.
- **CI-WINDOWS.** Both real Credential Manager tests passed on all three Windows legs. None skipped with error 1312.
- **M7-WIRING.** M7 wired every API in the integration notes. They are M7's verified criteria (M7-01, M7-02, M7-03,
  M7-09 and INT-M1B in [m7-integration.md](m7-integration.md)).

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then the plan's 28 Windows drills that still apply and its 6 Linux drills (in WSL), every one green,
red and green again. Five Windows drills mutated text that later merges rewrote. They are listed in
[wave4/drills-left-out.txt](reports/m1b/wave4/drills-left-out.txt). Two criteria had no other drill: AC-M1B-05 (the
stale-folder tidy now runs on its own thread) and AC-M1B-12 (the stream's pieces are emitted in `_reply_read`). They have
new ones, W4-M1B-05-stale-folders and W4-M1B-12-partial, both green, red and green. The requirements were reviewed
again against the amended rules ([wave4/readiness.md](reports/m1b/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M1B on fb19cb9.
