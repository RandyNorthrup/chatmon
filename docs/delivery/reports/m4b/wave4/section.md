## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI run this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered.** CI run 43677128712 on fb19cb9, which includes `CommandPlayer.close`, every job green. Each leg's
result for this plan's tests is in [reports/m4b/ci/observed.txt](reports/m4b/ci/observed.txt).

- **CI-WINDOWS-TOASTS: resolved.** Both toast tests passed on the three Windows legs. Those runners take the tests'
  notifications-on branch: run 43648733348's traceback fails inside `if notifications_on():`
  ([reports/m4b/ci/](reports/m4b/ci/)). So AC-03E's behavior was observed where Windows shows toasts.
- **CI-MACOS: resolved.** The module imports, Carbon's hotkey (registered, heard, a conflict reported) and NSSound passed
  on all three macOS legs.
- **CI-LINUX: resolved.** The imports, the X11 grab with and without NumLock, the GlobalShortcuts portal tests and the
  Linux players passed on the Ubuntu legs. Every warning is an error now, so the two ResourceWarnings are gone too.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then the plan's 36 Windows drills and its 6 Linux drills (in WSL) that still apply, every one green,
red and green again. Two of the Linux drills' texts have gone. L-01F-no-portal's criterion has other drills. AC-02E got
W4-L-02E-linux-player, on the `servers = {...}` line that replaced the old one, which also went green, red and green. The
requirements were reviewed again against the amended rules ([wave4/readiness.md](reports/m4b/wave4/readiness.md)).
T-SOUND-LINUX, T-HOTKEY-X11 and T-PORTAL are now verified.

**What remains: four red drills that need a place to run.**

| Criterion | What its drill needs | Owner |
|---|---|---|
| AC-00C (the imports on macOS) | macOS | Randy on a Mac, or the coordinator with a throwaway drill branch on CI |
| AC-01D (Carbon's hotkey) | macOS | the same |
| AC-02F (NSSound) | macOS | the same |
| AC-03E (a toast Windows shows) | a Windows desktop with notifications on. This PC's user has them off (`ToastEnabled = 0`), which isn't this worker's to change. | Randy: turn them on here for one run, approve a run on a test PC's signed-in desktop, or have the coordinator run a drill branch on CI |

Each is a deferred red receipt (W4-RED-AC-...-deferred) saying how to run it. T-IMPORTS-POSIX, T-HOTKEY-MAC,
T-SOUND-MAC and T-TOAST-SHOWN stay implemented until then.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.
