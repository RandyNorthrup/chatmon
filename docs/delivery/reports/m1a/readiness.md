# M1A readiness review, 2026-11-14

A review of the requirements in [m1a-security-updates.md](../../m1a-security-updates.md) against the brief
(ASSESSMENT.md, M1A section and M6A-14), ROADMAP.md (ownership, contracts, rules) and the code at `5346385`.
It checks the requirements, not the code: no behavior is claimed here.

## Coverage

Every assessment item in scope has one requirement with the same ID, and every requirement has at least one
acceptance criterion with an owning task:

| Requirement | Acceptance | Task |
|---|---|---|
| M1A-01 | AC-01-VERIFY, AC-01-LINUX, AC-01-MACOS, AC-01-USER | T-01, T-02, T-03 |
| M1A-02 | AC-02 | T-04 |
| M1A-03 | AC-03 | T-05 |
| M1A-04 | AC-04 | T-06 |
| M1A-05 | AC-05 | T-07 |
| M1A-06 | AC-06 | T-08 |
| M1A-07 | AC-07 | T-09 |
| M1A-08 | AC-08 | T-10 |
| M1A-09 | AC-09-ORDER, AC-09-REMOTE | T-11 |
| M1A-10 | AC-10 (manual, documentation only) | T-05 |
| M1A-11 | AC-11 | T-12 |
| M1A-12 | AC-12 | T-13 |
| M6A-14 | AC-M6A-14 | T-14 |

Each "Done when" bullet maps to a clause of an acceptance criterion; the security criteria name the refusals
the check itself must make (tampered list, bad signature, older version), as the coordinator required.

## Findings and how the plan resolves them

1. **Test isolation and M1A-11 (material).** Tests that isolate Chatmon's folders by setting `APPDATA` alone
   (`tests/test_app_smoke.py`, M0's; `tests/test_windows.py`, M6A's) would read and write the real
   `%LOCALAPPDATA%\chatmon` once state moves there. This PC has a real Chatmon (`%APPDATA%\chatmon` exists).
   Resolution: every local run of the suite and the drills sets `LOCALAPPDATA` to a scratch folder; M1A's own
   tests set it; an integration note asks M6A to set it in `tests/conftest.py` and M0/M6A to add it to their
   fixtures, before or with M1A's merge.
2. **CI calls the old helper interface.** `.github/workflows/packages.yml` (M6A's) runs
   `install-update FILE SHA256` on the package just built. After M1A-01 that call fails (wrong arguments), and
   a fresh build has no release signature. Resolution: `packaging/linux/test-install-update.sh` runs the real
   root path in a container with a throwaway key written into the installed check (root may change root's
   files); the integration note gives the replacement steps. The "update from the last release" step keeps
   working until a release with the new helper is the last one; the note covers that too.
3. **Users who lose something.** Two refusals change what some users get, by design: a Chatmon.app dragged from
   the .dmg (owned by the user) is no longer updated in place (it can't vouch for its own helper), and a
   `/usr/local/bin` owned by the user (Homebrew on Intel Macs) no longer gets a `chatmon` command from the
   installer. Both go into README notes with what to do instead.
4. **A real revoked certificate can't be made here.** Producing a revoked Authenticode chain needs a test root
   CA in the machine's trusted store (administrator rights, and a change to this shared PC's trust). AC-05 is
   covered at Windows' answer: a test drives `wintrust.signer` through a stand-in for `WinVerifyTrust` that
   returns `CERT_E_REVOKED` and checks the request asks for whole-chain revocation, and the real API is called
   with those flags on a genuinely signed file. Recorded as a limit in the closing report, not hidden.
5. **Platform-only criteria.** AC-01-MACOS runs only on macOS; AC-01-LINUX and AC-02 on Linux and macOS (AC-02
   is written with `ls -ldn` so it runs on both). Locally, Linux runs go through WSL (Arch, Python 3.14) in a
   private virtual environment; macOS is CI only. These are pending operations until CI reports.
6. **An M6A test calls `agents._run_json` directly** (`test_runs_an_npm_installed_tool`), and GitHub's Windows
   runners are elevated. Gating `_run_json` itself would fail that test in CI, so the gate is a wrapper used by
   the two agents with command lines; `test_agents.py` pins `elevated()` to False for tests not about it.
7. **Terminology.** "Root side" means the code that runs as root (Linux `install-update` and `verify-update`;
   macOS the root shell code and the bundle's `install-update`). "Signed list" is `SHA256SUMS.txt` with a valid
   `SHA256SUMS.txt.sig`. Used consistently in the plan.
8. **Contradictions.** None between the brief and ROADMAP. ROADMAP's owner decision on attached text (stored
   only on this computer, non-roaming on Windows) is what M1A-11 delivers.
9. **Ordering.** T-02, T-03 and T-13 depend on T-01 (the shared check); T-08 on T-07 (both change
   `wintrust.py` and `updates.verify`). Nothing else is ordered.

Result: ready to implement, with findings 1, 2 and 5 carried as integration notes and pending operations.
