# M1A: security, updates, IPC and packaging

The brief is [ASSESSMENT.md](ASSESSMENT.md#m1a-security-updates-ipc-and-packaging-updatespy-wintrustpy-eventspy-winpipepy-pathspy-agentspy-attachmentspy-packaging),
items M1A-01 to M1A-12, plus M6A-14 (the release-notes pin, which lives in `packaging/build.py`). The rules are
[ROADMAP.md](ROADMAP.md) (file ownership, contracts, rules for workers) and `pyproject.toml` (ruff, pytest).
Branch `wave1/m1a`, worktree `chatmon-wt/m1a`, from `improve/assessment-fixes` at `5346385`. Reports, logs and
drill specs are in [reports/m1a/](reports/m1a/).

## Scope and non-goals

In scope: every M1A item and M6A-14, in the files ROADMAP gives M1A, new files, and their tests. Priorities, as
the coordinator set them: M1A-01 first, then M1A-03, M1A-02, M1A-04, then the rest.

Not in scope (each goes to Integration notes instead): `app.py`, `cli.py` (M0), `chats.py`, `settings.py`,
`brains.py` (M1B), `.github/**`, `tests/conftest.py`, `tests/test_windows.py` (M6A), `README.md`,
`chatmon/changelog.md`, `chatmon/__init__.py`, `chatmon/settingswin.py`, and `packaging/README.md`, which nobody
owns in wave 1. Distribution (notarization, PyPI, AUR, winget) stays deferred.

## Re-checked findings

Every item was read against the code at `5346385` before planning.

| ID | Re-check |
|---|---|
| M1A-01 | Real. `install-update` takes `FILE SHA256` from the caller and installs any package named chatmon with that hash; macOS's osascript does the same with the hash from the environment. No version check anywhere on the root side. |
| M1A-02 | Real. `postinstall` runs `mktemp /usr/local/bin/.chatmon.XXXXXX`, then `cat >` reopens it by name: a user who owns `/usr/local/bin` (Homebrew on Intel Macs) can swap the name for a link between the two. |
| M1A-03 | Real. `_send_pipe` uses `QLocalSocket`, whose `CreateFile` has no `SECURITY_SQOS_PRESENT`, so a squatting server may impersonate the client at `SecurityImpersonation` level before the owner check runs. |
| M1A-04 | Real. `DisconnectAgents` runs `chatmon.exe hooks disconnect all` elevated in an install for everyone; `ClaudeCode` and `Muse` start `claude` and `muse` found on PATH or in user folders. |
| M1A-05 | Real. `fdwRevocationChecks = WTD_REVOKE_NONE`. |
| M1A-06 | Real. The installer runs from `%LOCALAPPDATA%\chatmon\updates` after its check, with nothing holding it. |
| M1A-07 | Real. `shutil.copy2` keeps the original's mode; nothing prunes. |
| M1A-08 | Real, coordinator-verified. `^\s*\[` matches `  [1, 2],` inside a multi-line array. |
| M1A-09 | Real. `os.open` runs before any check; network paths are only `\\` and `//` in `app.py`. |
| M1A-10 | Real. Nothing calls `client_is_me`; the module docstring says Chatmon checks each client. What keeps other users out is the pipe's DACL (`claim`'s, and Qt's `UserAccessOption`). |
| M1A-11 | Real. `_base` returns `%APPDATA%` (Roaming) for both config and state on Windows. `chats.py`, `memory.py` and `settings.py` all go through `paths.state_dir()` / `config_file()` / `state_file()`, so moving them is a `paths.py` change alone. |
| M1A-12 | Real. `install_kind()` has one test (the editable case); `install()` past the re-check, `_installed`, `relaunch_command` and `installer_command` for deb/rpm are untested. |
| M6A-14 | Real. `notes()` prints `pipx install --force git+https://github.com/RandyNorthrup/chatmon`. |

## Design

### M1A-01: root checks the signature and the version itself

A new standard-library module, `chatmon/releasecheck.py`, holds what both sides of an update must agree on:
the release keys (moved from `updates.py`, which re-exports them), the `SHA256SUMS.txt` reader, the signed-list
check, the release file names, and `check(kind, package, sums, signature, installed)`. `check` finds the
package's SHA-256 in a list the release key signed, takes the version from the name the list gives it (the
signature covers the name, so the version is the signer's word), and refuses anything not newer than
`installed`, which defaults to the checking package's own `__version__`: on the root side that is the installed
Chatmon, by construction. It imports only `chatmon/ed25519.py` (verification) and `changelog.version_key`,
both standard library. Its `main()` is the root-side command line: exit 0 and the version, or exit 3 and why.

- **Linux.** `packaging/linux/verify-update` (installed 0755 by `nfpm.yaml` at `/usr/lib/chatmon/verify-update`)
  checks that `/usr/lib/chatmon`, the `chatmon` folder, its `__pycache__` and the four modules it loads are owned
  by root, are not links, and nobody else can write them, then loads `chatmon.releasecheck` from
  `/usr/lib/chatmon` alone. `install-update` now takes `FILE SHA256SUMS.txt SHA256SUMS.txt.sig` (never a
  checksum), copies all three into a root-only `mktemp -d`, runs `/usr/bin/python3 -I -S
  /usr/lib/chatmon/verify-update KIND ...` on the copies, keeps the package-name check, and installs only on
  exit 0.
- **macOS.** No system Python, so the verifier is the app's own frozen Python:
  `packaging/macos/entry.py` (the spec's entry from now on) runs `chatmon.releasecheck.main` for
  `Chatmon verify-update ...`, and the CLI otherwise. Root's code (a constant in `updates.py`, handed to
  `/bin/sh -c` by the AppleScript as data) copies `/Applications/Chatmon.app` into a root-only `mktemp -d` with
  `ditto --noqtn`, refuses unless every entry of the copy is owned by root and writable by no group or other
  (checking the copy leaves no moment to swap the app between check and use; a user can't make root-owned
  files), and only then runs the copy's `Contents/Resources/install-update` (`packaging/macos/install-update`,
  put there by `build.py`), which copies the package and list in, runs the copied app's `verify-update`, and
  runs `installer`. `build.py` passes `--ownership recommended` to `pkgbuild` explicitly. A Chatmon.app that
  isn't root's (dragged from the .dmg) is no longer offered self-update: `install_kind()` says `manual` and
  points at the release page.
- **User side.** The updater keeps the signed list and signature it checked beside the download
  (`<name>.SHA256SUMS.txt`, `<name>.SHA256SUMS.txt.sig`) and hands all three to the root side.

### M1A-02: macOS postinstall

`/usr/local/bin` (and `/usr/local`, `/usr`) must be real folders owned by root, writable by nobody else, with
no ACL (`ls -ldn`, portable to Linux for tests). The script is built in a root-only `mktemp -d` and `mv`'d into
place (rename never follows a link at the destination). A refused folder means no `chatmon` command; the
README note says how to add one.

### M1A-03 and M1A-10: the pipe client

`winpipe.deliver(name, data, timeout_ms)` opens the pipe with `CreateFileW(..., FILE_FLAG_OVERLAPPED |
SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION)`, waits out a busy pipe with `WaitNamedPipeW`, checks
`server_is_me` on that handle, writes, then waits for the ack, all overlapped with deadlines (cancelled I/O is
waited for before its buffers are freed). `events._send_pipe` uses it, so hooks no longer need Qt on Windows.
The docstrings are made true: the DACL keeps other users out; `client_is_me` is offered for `_accept` (M7).

### M1A-04: elevated means files only

`agents.elevated()` (Windows `TokenElevation`, POSIX euid 0; fails closed) gates `_agent_cli`, the one wrapper
through which Claude Code's and Muse's command lines are started. Elevated, Claude Code is disconnected by
removing the marketplace copy Chatmon published (Claude Code drops a plugin whose marketplace folder is gone);
Muse says to disconnect it as yourself. The `.iss` comment says so. `_run_json` stays the runner (an M6A test
calls it directly).

### M1A-05: revocation

`WTD_REVOKE_WHOLECHAIN` with `WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT`. `CERT_E_REVOKED` reads "Revoked"; an
offline lookup (`CRYPT_E_REVOCATION_OFFLINE`, `CRYPT_E_NO_REVOCATION_CHECK`, `CERT_E_REVOCATION_FAILURE`) reads
"RevocationUnknown". `updates.verify` refuses both; the second as `TryLater`, for which the updater schedules a
retry in an hour, and at install time keeps the download.

### M1A-06: the Windows installer can't be swapped

At install, the verified download is copied into a fresh `mkdtemp` under the updates folder, held there with a
`GENERIC_READ`, `FILE_SHARE_READ`-only handle (`wintrust.hold`: no one can write, rename or delete it, nor rename
its folder), checked again through that state, and launched from there; the handle lives until Chatmon quits.
Old install folders are removed at the next check.

### M1A-07, M1A-08: agent files

Backups are written `O_CREAT|O_EXCL` at 0600 (a `-2`, `-3`... suffix within one second) and only the newest 5
per file are kept. Codex's notify line goes before the first line that isn't blank or a comment (always
top-level), and both connect and disconnect compare the parsed document before and after, refusing any change
but `notify`.

### M1A-09: attachments

Order: refuse network locations, `os.stat` (regular file, size), open non-blocking, `fstat` (still regular, same
`st_dev`/`st_ino`). Network: `\\`, `//`, and on Windows `GetDriveTypeW == DRIVE_REMOTE` (also for a link's
target); Linux `statfs` NFS, SMB/CIFS/SMB2 and FUSE (except `fuseblk`, a local disk, read from
`/proc/self/mountinfo`); macOS `statfs` without `MNT_LOCAL`.

### M1A-11: state stays on this computer

On Windows, config and state live under `%LOCALAPPDATA%\chatmon` (same layout). `migrate()` moves
`%APPDATA%\chatmon` there once: a rename when possible, otherwise a merge (a file in both: the newer wins) with a
copy across volumes (folder redirection), removing what it moved; anything locked is finished at the next start.
The old-name rename (penguin-companion) runs first, in Roaming, as before.

### M1A-12, M6A-14

Tests for `install_kind()` (every branch, with the package queries a module constant so a real program stands
in), `installer_command`, `relaunch_command`, and `install()` through `_installed` with a real child process.
`notes()` pins `@v{version}`.

## Reuse decisions

- `ed25519.py` is reused unchanged on both sides; no second verifier.
- `changelog.version_key` is reused for version order.
- `releasecheck.py` is new because the root side must not import Qt (`updates.py` does) and both sides must share
  one definition of names, keys and the check.
- `packaging/linux/verify-update` follows the existing `packaging/linux/chatmon` launcher pattern.
- `packaging/macos/entry.py` is new because `packaging/entry.py` isn't M1A's and Windows' Nuitka build must not
  change; it differs by the `verify-update` dispatch only.
- Tests sign with `tests/ed25519_sign.py`, a test-only RFC 8032 signer (checked against RFC 8032's vectors and,
  where it is installed, OpenSSL), since the standard library can't sign and no dependency may be added.

## Verification

- Whole suite and ruff before each commit, with `LOCALAPPDATA` pointed at a scratch folder (see Integration
  notes: tests that isolate only `APPDATA` would otherwise reach the real one once M1A-11 lands).
- POSIX shell scripts are tested by running a copy whose root uid, fixed paths and package-manager commands are
  replaced with test values; locally under WSL (Arch, Python 3.14) where possible, and on Linux/macOS CI.
- Red drills: `docs/delivery/reports/m1a/drill-spec.json` (Windows) and `drill-spec-linux.json` (run by the same
  harness under WSL), both through `tests/drills/run.py`.
- Platform-only checks that can't run here are recorded as pending operations in the checkpoint.

## Results

All in [reports/m1a/](reports/m1a/), against the code at `6c65c95`:

| Check | Result | Log |
|---|---|---|
| `ruff check .` | clean | `ruff.log` |
| Whole suite, Windows, plain command | 573 passed, 90 skipped, **7 failed**: all in other milestones' fixtures that isolate only `APPDATA` or use the real pipe name (Integration notes 1) | `pytest-windows.log` |
| Whole suite, Windows, with the conftest isolation of Integration notes 1 (`m1a_isolation.py`) | 579 passed, 90 skipped, 1 failed: M1B's `test_a_redirect_never_takes_the_key_anywhere` timing out under load, which passed 3 of 3 alone (`brains.py` is untouched) | `pytest-windows-isolated.log` |
| M1A's test files, Linux (WSL Arch, Python 3.14.9, PyQt 6.11.0) | 200 passed, 26 skipped (macOS and Windows only) | `pytest-linux.log` |
| Red drills, Windows | 19 of 19 green, red, green | `drills.log`, `drills.json` |
| Red drills, Linux (WSL) | 8 of 8 green, red, green | `drills-linux.log`, `drills-linux.json` |
| shellcheck 0.11.0 on every sh script and the macOS root code | clean | `shellcheck.log` |
| `nfpm` 2.48.0 build of the .deb and .rpm (WSL) | both carry `/usr/lib/chatmon/verify-update` and `install-update` at 0755 root:root, and `chatmon/releasecheck.py` | (observed; no artifact kept) |

Not run here, pending CI: the macOS tests (AC-01-MACOS's root code and checked app copy, the AppleScript
hand-off, `_mac_statfs`, AC-02 under BSD `ls`), and `packaging/linux/test-install-update.sh` in containers.
Known limit: no real revoked Authenticode chain could be made on this shared PC (it needs a test root in the
machine's trust store); AC-05 is shown at Windows' own answer and with the real API's revocation flags.

Two things found on the way and fixed in M1A's own tests: `test_events.py::test_send_without_a_running_companion`
used the real pipe name on Windows and told a running Chatmon (the owner's, on this PC) to show itself; and the
scratchpad is shared between workers, so M1A's scratch files moved to a folder of their own.

## Integration notes

1. **Test isolation on Windows (M6A's `tests/conftest.py`; M0's and M6A's tests). Needed with M1A's merge.**
   Config and state now live under `%LOCALAPPDATA%`, and the pipe is named after your account whatever the
   folders. Add to `tests/conftest.py` (the code is `reports/m1a/m1a_isolation.py`):
   `os.environ.setdefault("CHATMON_INSTANCE", f"test-{os.getpid()}")` at import, and an autouse fixture doing
   `monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))`. Then, in `tests/test_windows.py`,
   `test_the_pipe_is_named_for_you_and_this_session` must `monkeypatch.delenv("CHATMON_INSTANCE")` (it checks
   your own pipe's name). Without these, on Windows: `test_app_smoke.py::test_a_hook_reaches_it` (its hook can
   reach a real running Chatmon: the cause of its flakiness), five chat tests in `test_app_smoke.py` (state
   shared between tests), and `test_windows.py::test_without_a_console_it_keeps_a_log` fail. With them the
   whole suite passes (see Results). M0's `companion` fixture may also set `LOCALAPPDATA` itself.
2. **`packages.yml` (M6A).** `install-update` now takes `FILE SHA256SUMS.txt SHA256SUMS.txt.sig`. In the Linux
   job's "Install each on a fresh system" step, replace the two `install-update ... $sum` lines per image with
   `sh /src/packaging/linux/test-install-update.sh /src/dist/chatmon_*_all.deb` (ubuntu, debian) and
   `... /src/dist/chatmon-*.noarch.rpm` (fedora), run as root in the container after the package is installed:
   it makes a throwaway release key, installs an older Chatmon that trusts it, and checks refusals and the
   install. The "update from the last release" step keeps working (it runs the last release's own helper)
   until a release with the new helper is the last one; from then it needs this script's approach too.
   Suggested for the macOS job: `test -x /Applications/Chatmon.app/Contents/Resources/install-update`,
   `[ "$(stat -f %u /Applications/Chatmon.app)" = 0 ]`, and `Chatmon verify-update macos x y z` exiting 3.
3. **M7 / M0 (`app.py`).** APIs delivered, all in M1A's files:
   - `winpipe.client_is_me(handle)`: `_accept` may call it with `int(sock.socketDescriptor())` on Windows and
     abort a connection it says no to (the pipe's access list already keeps other users out).
   - `winpipe.deliver(name, data, timeout_ms) -> "sent" | "absent" | "foreign"`; `events.deliver` uses it.
   - `updates.installer_command(kind, path)` (no checksum argument any more), `updates.sums_for(download)`,
     `updates.prepare(download, expected, kind) -> Prepared | str`, `updates.TryLater` (a `str`),
     `Updater.retry` (a `QTimer`, `RETRY_AFTER` seconds), `updates.root_owned(app)`.
   - New failure wording: "The update wasn't installed yet: …" (kept, retried) and root's own sentence
     "The update wasn't installed: …". `_update_failed` already shows anything starting "The update".
   - `attachments.network_location(path)`; `_attach_files_named`'s own `//` and `\\` filter can stay or go.
   - `agents.elevated()`; `paths.instance()` and `paths.INSTANCE_ENV` (`CHATMON_INSTANCE`).
4. **M1B.** Nothing to change: `chats.py`, `memory.py` and `settings.py` already reach their files through
   `paths`, so they move with it.
5. **Coordinator (`.gitattributes`, unowned).** Add `text eol=lf` for `packaging/linux/install-update`,
   `packaging/linux/verify-update` and `packaging/macos/install-update`, as for the other sh scripts, so a
   Windows checkout keeps them runnable (Linux builds run on Linux checkouts, and `build.py` normalizes the
   macOS one, so releases aren't affected).
6. **`packaging/README.md` (unowned).** Its "Updates" paragraph should say root's side checks the signed list
   and the version itself, from `/usr/lib/chatmon` or a checked copy of Chatmon.app, and that the macOS .pkg
   installs the app as root's.
7. **M6A-10 (`CONTRIBUTING.md`).** Worth a line: `CHATMON_INSTANCE=<name>` runs a Chatmon apart from yours.

## Changelog notes

- **Security:** On Linux and macOS, installing an update now has the system itself check the release's signed
  list of checksums and its version: it installs only a newer Chatmon signed by its release key, whatever it's
  handed. On macOS that check uses Chatmon's own code from the app the installer put in Applications.
- **Security (Windows):** Your coding agents' hooks reach Chatmon in a way that never lets whoever holds its
  address act as you.
- **Security (Windows):** Updates check that the signing certificate hasn't been revoked. If Windows can't
  check (you're offline), the update waits, and Chatmon looks again within the hour.
- **Security (Windows):** The update's installer runs from a copy that nothing can change between its check and
  its start.
- **Security:** Uninstalling a Chatmon installed for everyone no longer starts Claude Code's or Muse Code's
  programs as an administrator.
- **Security (macOS):** The installer adds the `chatmon` command only to a `/usr/local/bin` that belongs to the
  system.
- Backups of your coding agents' settings are readable by you alone, and only the newest five are kept.
- Files on network drives, shares and FUSE mounts can't be attached any more: copy them to this computer first.
- **Windows:** Settings and chats moved from the roaming profile to this computer
  (`%LOCALAPPDATA%\chatmon`), automatically, the first time this version starts.
- Fix: Codex settings with an array of arrays across lines couldn't be connected.
- Release notes' pipx command now installs that release, not the latest code.

## README notes

- Windows: settings are in `%LOCALAPPDATA%\chatmon\config.toml` and chats and state in
  `%LOCALAPPDATA%\chatmon\state` (they were under `%APPDATA%`), so chats and attached text stay on this
  computer, as the privacy section promises; older ones are moved there automatically.
- Updates: on macOS and Linux the system checks the release's signature and version itself before installing.
  On macOS, Chatmon updates itself when it was installed with the .pkg; a Chatmon.app dragged from the .dmg
  says where to download the new .pkg (installing it once makes later updates automatic).
- macOS: if `/usr/local/bin` belongs to you (Homebrew on Intel Macs), the installer doesn't add `chatmon`;
  `ln -s /Applications/Chatmon.app/Contents/MacOS/Chatmon /usr/local/bin/chatmon` adds it.
- Attachments: only files on this computer (not network drives, shares or FUSE mounts).
- Uninstalling a Chatmon installed for everyone disconnects your agents by editing their files; Muse Code's
  plugin can only be removed with `chatmon hooks disconnect muse`, run as yourself.

## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI runs this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time. One of them, followups, is
changing packaging and the requirements. Their merges will make some of these receipts stale again.

**What the runs answered.** Every leg's result for this plan's tests is in
[reports/m1a/ci/observed.txt](reports/m1a/ci/observed.txt).

- **CI-MACOS: resolved.** In CI run 43677128712 on fb19cb9, with every job green, the macOS tests passed on all three
  macOS legs: the root code with a checked copy of Chatmon.app, the AppleScript hand-off, the postinstall under BSD
  `ls`, and the `statfs` mount check. In PR #18's Packages run 43677664360, on fb19cb9's own tree, the macos-latest and
  macos-15-intel jobs installed the built .pkg. Chatmon.app was root's, with `install-update` inside it, and its own frozen `verify-update` refused missing
  files with exit 3.
- **CI-CONTAINER: resolved.** In the same run, and in the earlier 43675230966, `packages.yml`'s Linux job ran `packaging/linux/test-install-update.sh`, root's real path,
  in ubuntu:24.04, debian:trixie and fedora:44 containers ("all good" three times), with no caller's checksum.
- **MERGE-ISOLATION: resolved.** `tests/conftest.py` gives every test its own `LOCALAPPDATA` and `CHATMON_INSTANCE`, and
  the whole suite passes on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241 passed, 148
  skipped). It passes on CI's three Windows legs too.

**What was re-run.** The plan's 17 Windows drills that still apply and its 8 Linux drills (in WSL), every one green, red
and green again. Two Windows drills mutated text that later merges rewrote. Their criteria have other drills
([wave4/drills-left-out.txt](reports/m1a/wave4/drills-left-out.txt)). AC-10's docstrings were read again against the
code ([wave4/review-ac10.md](reports/m1a/wave4/review-ac10.md)). They still hold, and `app.py`'s accept path now makes the
`client_is_me` check they offer. The requirements were reviewed again against the amended rules
([wave4/readiness.md](reports/m1a/wave4/readiness.md)).

**What remains.** AC-01-MACOS's red drill. Its behavior is now observed on macOS, but proving its test would notice the
ownership check going (`! -user root -o -perm +022` in `_MACOS_ROOT`) needs a run on macOS: `ditto`, BSD `find` and
`osascript`. No Mac is here or in the test lab, and a CI run of a drill branch needs a push, which this worker may not
make. It is recorded as a deferred red receipt, W4-RED-AC-01-MACOS, which says how to run it. T-03-macos-root stays
implemented until it is done. Owner: Randy on a Mac, or the coordinator with a throwaway drill branch on CI.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.

## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 17 Windows drills and 8 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its Linux and macOS legs, with PR #18's Packages run 43701523037 on bf9d8ac (the containers' and macOS's root-side checks) ([reports/m1a/ci/observed-bf9d8ac.txt](reports/m1a/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m1a/wave4b/readiness.md)).

AC-10's docstrings were read again ([wave4b/review-ac10.md](reports/m1a/wave4b/review-ac10.md)), and they hold.

**What remains.** AC-01-MACOS's red drill still needs macOS. It is recorded again as W4B-RED-AC-01-MACOS, which says
how to run it. Owner: Randy on a Mac, or the coordinator with a throwaway drill branch on CI.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them.

## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** None of round two's receipts bound those files. But ROADMAP.md is a rule of
every plan, and round three amends it (the Outcome at 3586a0d), so every receipt went stale with it. Every
check was run again on 3586a0d or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 17 Windows drills and 8 Linux ones (in WSL). Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Linux and macOS legs, with PR #18's Packages run 43729628343 on 3586a0d (the containers' and macOS's root-side checks)
([reports/m1a/ci/observed-3586a0d.txt](reports/m1a/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m1a/wave4c/readiness.md)).

AC-10's docstrings were read again ([wave4c/review-ac10.md](reports/m1a/wave4c/review-ac10.md)), and they hold.

**What remains.** AC-01-MACOS's red drill still needs macOS, as in round two. It is recorded again as
W4C-RED-AC-01-MACOS, which says how to run it. Owner: Randy on a Mac, or the coordinator with a throwaway drill
branch on CI.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M1A",
    "title": "Security, updates, IPC and packaging",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "3586a0d+wave4c"
      },
      {
        "path": "pyproject.toml",
        "revision": "3586a0d"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py",
      "docs/delivery/reports/wave4/cilog.py",
      "docs/delivery/reports/wave4/wsl_drills.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    }
  },
  "requirements": [
    {
      "id": "M1A-01",
      "statement": "The root side of an update verifies the signed SHA256SUMS and its signature itself, with the key in root-owned code run by python3 -I (Linux) or a root-owned helper inside Chatmon.app (macOS), and requires a version newer than the one installed",
      "priority": "critical",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-02",
      "statement": "The macOS postinstall refuses a /usr/local/bin that isn't root-owned or is group/world-writable, and builds the command file in a root-only mktemp -d before mv",
      "priority": "critical",
      "acceptance": [
        "AC-02"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-03",
      "statement": "The Windows pipe client opens the pipe with CreateFileW and SECURITY_SQOS_PRESENT|SECURITY_IDENTIFICATION, then checks the server and writes on that handle",
      "priority": "critical",
      "acceptance": [
        "AC-03"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-04",
      "statement": "Elevated processes only edit agents' files and never start agents' command lines",
      "priority": "critical",
      "acceptance": [
        "AC-04"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-05",
      "statement": "Windows signature checks check revocation; an offline lookup is retried later, never passed; a revoked certificate fails",
      "priority": "critical",
      "acceptance": [
        "AC-05"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-06",
      "statement": "The verified Windows installer can't be swapped between its check and its launch",
      "priority": "critical",
      "acceptance": [
        "AC-06"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-07",
      "statement": "Agent config backups are created 0600 with O_CREAT|O_EXCL and only the last 5 per file are kept",
      "priority": "normal",
      "acceptance": [
        "AC-07"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-08",
      "statement": "Valid Codex configs are accepted, and connect then disconnect leaves every other key unchanged",
      "priority": "normal",
      "acceptance": [
        "AC-08"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-09",
      "statement": "Attachments are stat-checked before opening and fstat-checked after, and network locations are refused on every OS",
      "priority": "normal",
      "acceptance": [
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-10",
      "statement": "winpipe's docstrings say truly how clients are kept out, and client_is_me is offered for accept",
      "priority": "low",
      "acceptance": [
        "AC-10"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-11",
      "statement": "On Windows, chats and other state live under %LOCALAPPDATA%\\chatmon, moved there once from Roaming, leaving nothing behind",
      "priority": "normal",
      "acceptance": [
        "AC-11"
      ],
      "superseded_by": null
    },
    {
      "id": "M1A-12",
      "statement": "install_kind() and the install and relaunch code are covered by tests",
      "priority": "normal",
      "acceptance": [
        "AC-12"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-14",
      "statement": "Release notes pin pipx installs to @v{version}",
      "priority": "low",
      "acceptance": [
        "AC-M6A-14"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-01-VERIFY",
      "requirement": "M1A-01",
      "given": "A SHA256SUMS.txt signed by a throwaway key the check is told to trust, and a package listed in it",
      "when": "releasecheck.check or releasecheck.main runs on the package, the list and the signature",
      "then": "A listed package newer than the installed version passes and its version is printed; a tampered list, a bad signature, a version not newer, an unlisted package and another kind's name are each refused by the check itself (main exits 3)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-LINUX",
      "requirement": "M1A-01",
      "given": "install-update and verify-update as installed, with root's uid, fixed paths and the package manager replaced by test values",
      "when": "install-update runs with FILE SHA256SUMS.txt SHA256SUMS.txt.sig",
      "then": "It copies all three into a root-only folder before checking, runs verify-update with python3 -I -S, installs the copy only when the verifier passes, refuses a tampered list, a bad signature and an old version, and verify-update refuses to load from a folder or file root doesn't own or others can write",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-MACOS",
      "requirement": "M1A-01",
      "given": "A copy of Chatmon.app and the root script, with root's uid, the app's path and installer replaced by test values",
      "when": "The root script runs on a package, its list and signature",
      "then": "It copies the app into a root-only folder, refuses a copy with any entry not root's or writable by group or others before running anything from it, runs the copied app's verify-update, and installs only when it passes",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-USER",
      "requirement": "M1A-01",
      "given": "A verified download for a deb, rpm or macOS install",
      "when": "The updater builds the command that installs it",
      "then": "The root side gets the download, the signed list and its signature, never a checksum to trust; a Chatmon.app not owned by root is not offered self-update",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02",
      "requirement": "M1A-02",
      "given": "The postinstall with root's uid and /usr/local/bin replaced by test values",
      "when": "It runs with a folder that is root's alone, one others can write, one owned by someone else, and a link",
      "then": "Only the first gets the chatmon command, written whole and executable, with no temporary file ever in that folder; the others are left untouched",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03",
      "requirement": "M1A-03",
      "given": "A pipe served in this process that tries to take on the identity of whoever connects",
      "when": "A hook delivers a message through it",
      "then": "The server gets SecurityIdentification at most, the message arrives and is acknowledged, a pipe served as someone else is told nothing, and a refused or absent pipe reads foreign or absent",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04",
      "requirement": "M1A-04",
      "given": "An elevated process (administrator or root) and an agent command line on PATH that would leave a mark if run",
      "when": "Agents are connected, checked or disconnected",
      "then": "No agent command line starts; file-based agents are still disconnected; Claude Code is disconnected by removing Chatmon's marketplace copy",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-05",
      "requirement": "M1A-05",
      "given": "Windows' signature check",
      "when": "A file is checked",
      "then": "Revocation is asked for the whole chain; a revoked certificate fails; an offline lookup fails as try-later, the updater retries within the hour and keeps a download it can't check at install time",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-06",
      "requirement": "M1A-06",
      "given": "A verified Windows installer",
      "when": "It is installed",
      "then": "A copy in a fresh folder is held so it can't be written, renamed or deleted, nor its folder renamed, from before its check until after it is launched from there",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07",
      "requirement": "M1A-07",
      "given": "An agent settings file changed many times",
      "when": "Each change makes a backup",
      "then": "Each backup is a new file readable by you alone, with the original's bytes, never overwriting another, and only the newest 5 are left",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-08",
      "requirement": "M1A-08",
      "given": "Generated valid Codex configs with multi-line arrays, tables, arrays of tables, comments and multi-line strings holding lines that look like table headers",
      "when": "Codex is connected, then disconnected",
      "then": "Connecting is accepted and adds only the top-level notify; disconnecting restores every other key exactly",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-ORDER",
      "requirement": "M1A-09",
      "given": "A path that isn't a regular file, or a file swapped between the look and the open",
      "when": "It is attached",
      "then": "A non-regular path is refused without being opened, and a swapped file is refused after the open",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-REMOTE",
      "requirement": "M1A-09",
      "given": "A UNC path, a mapped network drive, an NFS, SMB or FUSE mount (but not fuseblk), or a non-local macOS mount",
      "when": "It is attached",
      "then": "It is refused as a network location before it is opened or looked at, and local files still attach",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-10",
      "requirement": "M1A-10",
      "given": "winpipe's module and function docstrings",
      "when": "They are read against the code",
      "then": "They say the DACL keeps other users out, and client_is_me is described as a check offered to the accept path",
      "checks": [
        "manual"
      ],
      "manual_reason": "Documentation-only change: the behavior of client_is_me is unchanged and already covered by tests/test_windows.py::test_a_hooks_own_process_is_you"
    },
    {
      "id": "AC-11",
      "requirement": "M1A-11",
      "given": "Windows, with Chatmon's settings and chats in %APPDATA%\\chatmon",
      "when": "Chatmon starts",
      "then": "Config and state are read from %LOCALAPPDATA%\\chatmon, everything is moved there (merging with what is already there, the newer file winning, across volumes too), nothing is left in Roaming, and a locked file is finished next time",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-12",
      "requirement": "M1A-12",
      "given": "Each kind of install",
      "when": "install_kind, installer_command, relaunch_command and Updater.install run",
      "then": "Each kind is told apart, gets its own installer and relaunch commands, and a finished install relaunches and quits while a failed one says why and keeps Chatmon",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M6A-14",
      "requirement": "M6A-14",
      "given": "A version in chatmon/changelog.md",
      "when": "packaging/build.py notes runs for it",
      "then": "The pipx line installs git+https://github.com/RandyNorthrup/chatmon@v<version>",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-01-releasecheck",
      "purpose": "A Qt-free release check shared by the user and root sides, and the updater handing the root side the signed list instead of a checksum",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-USER"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/releasecheck.py",
          "action": "create"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "tests/ed25519_sign.py",
          "action": "create"
        },
        {
          "path": "tests/test_releasecheck.py",
          "action": "create"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-01-VERIFY-signature",
        "R-RED-AC-01-VERIFY-version",
        "R-RED-AC-01-USER-handoff",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-01-USER-handoff",
        "W4-RED-AC-01-VERIFY-signature",
        "W4-RED-AC-01-VERIFY-version",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-01-USER-handoff",
        "W4B-RED-AC-01-VERIFY-signature",
        "W4B-RED-AC-01-VERIFY-version",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-01-USER-handoff",
        "W4C-RED-AC-01-VERIFY-signature",
        "W4C-RED-AC-01-VERIFY-version"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-02-linux-root",
      "purpose": "Root's side on Linux: install-update checks through verify-update, installed by nfpm",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "depends_on": [
        "T-01-releasecheck"
      ],
      "changes": [
        {
          "path": "packaging/linux/install-update",
          "action": "modify"
        },
        {
          "path": "packaging/linux/verify-update",
          "action": "create"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "action": "modify"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "action": "create"
        },
        {
          "path": "tests/test_install_update.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-LINUX",
        "R-RED-AC-01-LINUX-launcher-owner",
        "R-RED-AC-01-LINUX-refusal-stops",
        "R-RED-AC-01-LINUX-installs-the-copy",
        "W4-READY",
        "W4-BEH-CI-LINUX",
        "W4-BEH-PKG-CONTAINERS",
        "W4-RED-AC-01-LINUX-installs-the-copy",
        "W4-RED-AC-01-LINUX-launcher-owner",
        "W4-RED-AC-01-LINUX-refusal-stops",
        "W4B-READY",
        "W4B-BEH-CI-LINUX",
        "W4B-BEH-PKG-CONTAINERS",
        "W4B-RED-AC-01-LINUX-installs-the-copy",
        "W4B-RED-AC-01-LINUX-launcher-owner",
        "W4B-RED-AC-01-LINUX-refusal-stops",
        "W4C-READY",
        "W4C-BEH-CI-LINUX",
        "W4C-BEH-PKG-CONTAINERS",
        "W4C-RED-AC-01-LINUX-installs-the-copy",
        "W4C-RED-AC-01-LINUX-launcher-owner",
        "W4C-RED-AC-01-LINUX-refusal-stops"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-03-macos-root",
      "purpose": "Root's side on macOS: a checked copy of Chatmon.app verifies the update with its own frozen Python",
      "acceptance": [
        "AC-01-MACOS",
        "AC-01-USER"
      ],
      "depends_on": [
        "T-01-releasecheck"
      ],
      "changes": [
        {
          "path": "packaging/macos/install-update",
          "action": "create"
        },
        {
          "path": "packaging/macos/entry.py",
          "action": "create"
        },
        {
          "path": "packaging/chatmon.spec",
          "action": "modify"
        },
        {
          "path": "packaging/build.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_install_update.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-BEH-MAC",
        "R-RED-MAC",
        "R-RED-AC-01-USER-handoff",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-01-MACOS",
        "W4-BEH-CI-MACOS",
        "W4-BEH-PKG-MACOS",
        "W4-RED-AC-01-USER-handoff",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-01-MACOS",
        "W4B-BEH-CI-MACOS",
        "W4B-BEH-PKG-MACOS",
        "W4B-RED-AC-01-USER-handoff",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-01-MACOS",
        "W4C-BEH-CI-MACOS",
        "W4C-BEH-PKG-MACOS",
        "W4C-RED-AC-01-USER-handoff",
        "MAC-RED-AC-01-MACOS"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-04-postinstall",
      "purpose": "The macOS postinstall writes only into a root-only folder, from a root-only temporary folder",
      "acceptance": [
        "AC-02"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "packaging/macos/scripts/postinstall",
          "action": "modify"
        },
        {
          "path": "tests/test_packaging.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-LINUX",
        "R-RED-AC-02-owner",
        "R-RED-AC-02-writable",
        "W4-READY",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-RED-AC-02-owner",
        "W4-RED-AC-02-writable",
        "W4B-READY",
        "W4B-BEH-CI-LINUX",
        "W4B-BEH-CI-MACOS",
        "W4B-RED-AC-02-owner",
        "W4B-RED-AC-02-writable",
        "W4C-READY",
        "W4C-BEH-CI-LINUX",
        "W4C-BEH-CI-MACOS",
        "W4C-RED-AC-02-owner",
        "W4C-RED-AC-02-writable"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-05-pipe-client",
      "purpose": "Hooks open Chatmon's pipe for identification only and check its server on that handle; winpipe's docstrings made true",
      "acceptance": [
        "AC-03",
        "AC-10"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/winpipe.py",
          "action": "modify"
        },
        {
          "path": "chatmon/events.py",
          "action": "modify"
        },
        {
          "path": "tests/test_winpipe.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-MAN-AC10",
        "R-RED-AC-03-sqos",
        "R-RED-AC-03-owner",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-MAN-AC10",
        "W4-RED-AC-03-owner",
        "W4-RED-AC-03-sqos",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-MAN-AC10",
        "W4B-RED-AC-03-owner",
        "W4B-RED-AC-03-sqos",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-MAN-AC10",
        "W4C-RED-AC-03-owner",
        "W4C-RED-AC-03-sqos"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-06-elevated",
      "purpose": "Elevated, agents.py edits files only and never starts an agent's command line",
      "acceptance": [
        "AC-04"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "action": "modify"
        },
        {
          "path": "tests/test_agents.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-04-gate",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-04-gate",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-04-gate",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-04-gate"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-07-revocation",
      "purpose": "Revocation is checked, a revoked certificate fails, and an offline lookup is retried",
      "acceptance": [
        "AC-05"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/wintrust.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wintrust.py",
          "action": "create"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-05-revocation-asked",
        "R-RED-AC-05-try-later",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-05-revocation-asked",
        "W4-RED-AC-05-try-later",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-05-revocation-asked",
        "W4B-RED-AC-05-try-later",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-05-revocation-asked",
        "W4C-RED-AC-05-try-later"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-08-held-installer",
      "purpose": "The Windows installer is launched from a held copy in a fresh folder",
      "acceptance": [
        "AC-06"
      ],
      "depends_on": [
        "T-07-revocation"
      ],
      "changes": [
        {
          "path": "chatmon/wintrust.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wintrust.py",
          "action": "modify"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-06-hold",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-06-hold",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-06-hold",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-06-hold"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-09-backups",
      "purpose": "Private, capped backups of agents' files",
      "acceptance": [
        "AC-07"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "tests/test_agents.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-BEH-LINUX",
        "R-RED-AC-07-prune",
        "R-RED-AC-07-private",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-RED-AC-07-private",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-BEH-CI-LINUX",
        "W4B-RED-AC-07-private",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-BEH-CI-LINUX",
        "W4C-RED-AC-07-private"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-10-codex",
      "purpose": "Codex's notify line placed where it is always top-level, with a parsed before/after check",
      "acceptance": [
        "AC-08"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "tests/test_agents.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-08-codex-top",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-08-codex-top",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-08-codex-top",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-08-codex-top"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-11-attachments",
      "purpose": "Attachments look before opening, check after, and refuse network locations on every OS",
      "acceptance": [
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/attachments.py",
          "action": "modify"
        },
        {
          "path": "tests/test_attachments.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-BEH-LINUX",
        "R-RED-AC-09-ORDER-swap",
        "R-RED-AC-09-ORDER-look-first",
        "R-RED-AC-09-REMOTE-drive",
        "R-RED-AC-09-REMOTE-linux",
        "R-RED-AC-09-ORDER-pipe",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-RED-AC-09-ORDER-look-first",
        "W4-RED-AC-09-ORDER-pipe",
        "W4-RED-AC-09-ORDER-swap",
        "W4-RED-AC-09-REMOTE-drive",
        "W4-RED-AC-09-REMOTE-linux",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-BEH-CI-LINUX",
        "W4B-BEH-CI-MACOS",
        "W4B-RED-AC-09-ORDER-look-first",
        "W4B-RED-AC-09-ORDER-pipe",
        "W4B-RED-AC-09-ORDER-swap",
        "W4B-RED-AC-09-REMOTE-drive",
        "W4B-RED-AC-09-REMOTE-linux",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-BEH-CI-LINUX",
        "W4C-BEH-CI-MACOS",
        "W4C-RED-AC-09-ORDER-look-first",
        "W4C-RED-AC-09-ORDER-pipe",
        "W4C-RED-AC-09-ORDER-swap",
        "W4C-RED-AC-09-REMOTE-drive",
        "W4C-RED-AC-09-REMOTE-linux"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-12-local-state",
      "purpose": "Windows config and state under %LOCALAPPDATA%, moved there once from Roaming",
      "acceptance": [
        "AC-11"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/paths.py",
          "action": "modify"
        },
        {
          "path": "tests/test_paths.py",
          "action": "create"
        },
        {
          "path": "tests/test_rename.py",
          "action": "modify"
        },
        {
          "path": "tests/test_agents.py",
          "action": "modify"
        },
        {
          "path": "packaging/build.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-11-local",
        "R-RED-AC-11-newer-wins",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-11-local",
        "W4-RED-AC-11-newer-wins",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-11-local",
        "W4B-RED-AC-11-newer-wins",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-11-local",
        "W4C-RED-AC-11-newer-wins"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-13-updater-tests",
      "purpose": "Tests for install_kind and the install and relaunch code",
      "acceptance": [
        "AC-12"
      ],
      "depends_on": [
        "T-01-releasecheck"
      ],
      "changes": [
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-12-kind",
        "R-RED-AC-12-relaunch",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-12-kind",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-12-kind",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-12-kind"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-14-notes-pin",
      "purpose": "Release notes pin pipx installs to the release's tag",
      "acceptance": [
        "AC-M6A-14"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "packaging/build.py",
          "action": "modify"
        },
        {
          "path": "tests/test_packaging.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "R-BEH-WIN",
        "R-RED-AC-M6A-14-pin",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-AC-M6A-14-pin",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-RED-AC-M6A-14-pin",
        "W4C-READY",
        "W4C-BEH-WINDOWS",
        "W4C-RED-AC-M6A-14-pin"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "R-READY-1",
      "acceptance": [
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER",
        "AC-01-VERIFY",
        "AC-02",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-10",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review: read every M1A item and M6A-14 in ASSESSMENT.md, the ROADMAP ownership, contracts and rules, and the code at 5346385; checked coverage, conflicts, terminology, failure behavior, platform reach and ordering; findings and resolutions recorded in the artifact",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/readiness.md",
        "sha256": "5214a0ee5961501ac7fee8b61cfa0cd0b61c9e2f6a62e632e9a7c87d64e86bb0"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "472b4f52cd7320e95bc40a11fa614d4e647de9bff7ed2a63d412dfd60bb97548",
      "red": null,
      "reason": "The plan's narrative gained its results and notes after this review; re-checked as R-READY-2."
    },
    {
      "id": "R-READY-2",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER",
        "AC-02",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-10",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Re-read the requirements, criteria and tasks after implementation against ASSESSMENT.md and ROADMAP.md: unchanged; the narrative gained results and notes, and the foreseen findings held (addendum in the artifact)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/readiness.md",
        "sha256": "2e86ced385bfed3f9af33b7277384feac05d07af3086591b27b21349e8cd4af6"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "b43b59657b6cb3c64e0048ffd0f4319b5a5ec5c957ed91977f06ab542b4e2e23",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-BEH-WIN",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-USER",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_releasecheck.py",
        "tests/test_install_update.py",
        "tests/test_packaging.py",
        "tests/test_updates.py",
        "tests/test_agents.py",
        "tests/test_attachments.py",
        "tests/test_paths.py",
        "tests/test_rename.py",
        "tests/test_events.py",
        "tests/test_winpipe.py",
        "tests/test_wintrust.py",
        "tests/test_chats.py"
      ],
      "method": "M1A's test files on Windows 11 with a fresh scratch LOCALAPPDATA: 180 passed, 46 skipped (POSIX- and macOS-only). The whole suite's runs (pytest-windows.log, pytest-windows-isolated.log) are context: their only failures are other milestones' fixtures and a timing flake, explained in the plan's Results",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/pytest-windows-m1a.log",
        "sha256": "34e19dcd42ba5a6d5d5ba485acf67ddc8107a49b9aaee0e557434fc17fcee575"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "b0bcbc335744ae3501f52b22c178d0337d2f312b6413c0c0e101f2ad2de71cde"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "1200fcd98e6e8159f3891b614f3e0a06b53505416ad8ff3840ac84d454063dbc"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "fa2ce42898ee87f0e9d89385c00e5fe1e3a678fecdb91694423cb82708021291"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2c50df70a31c5ae2a7aab3ac72e998a1ab3abb4b891014afcdaf31f53f2cf81c"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "499c62447c5360041f201b80d52418608086780c5c6c485f61dd07ee42ec6df1"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "aa2ecf9a26761228152bfb2ec94b8bb01f4a865f7eee69b9e2a1b945d1b73422"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "91d16c19f459d1c02754d555312907b64eed36e836fbf67b6f4dd045c7da70c3",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-BEH-LINUX",
      "acceptance": [
        "AC-01-LINUX",
        "AC-02",
        "AC-07",
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_releasecheck.py",
        "tests/test_install_update.py",
        "tests/test_packaging.py",
        "tests/test_updates.py",
        "tests/test_agents.py",
        "tests/test_attachments.py",
        "tests/test_paths.py",
        "tests/test_rename.py",
        "tests/test_events.py",
        "tests/test_winpipe.py",
        "tests/test_wintrust.py",
        "tests/test_chats.py"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. M1A's test files: 200 passed, 26 skipped (macOS- and Windows-only): the Linux root side for real as copies, the postinstall's folder checks, private backups, pipes and devices, statfs and mountinfo",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/pytest-linux.log",
        "sha256": "d45ad6476f84bc17b894fa0b1295c7d019921d37a43db7b12d0ebc0dc1037f96"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "58fcab51bbb2d8f29b5df25588f1d604dc6797387f6afa5fdc3bbad0ae0660d6"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "b70e0a81a7492dbdf4fcbc4677301b7d24708d022093c69976feb1cd257b5f00",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-BEH-MAC",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "behavior",
      "status": "deferred",
      "command": [],
      "method": "The macOS tests in tests/test_install_update.py (the root code with a checked copy of Chatmon.app, the AppleScript hand-off) need macOS: ditto, BSD find, osascript. None is available on this Windows host.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "1200fcd98e6e8159f3891b614f3e0a06b53505416ad8ff3840ac84d454063dbc"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "fa2ce42898ee87f0e9d89385c00e5fe1e3a678fecdb91694423cb82708021291"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2c50df70a31c5ae2a7aab3ac72e998a1ab3abb4b891014afcdaf31f53f2cf81c"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "d3220231abc53fa831d8531ab81e24e46898d16d02dbe55f86a5687919f67126",
      "red": null,
      "reason": "macOS only; next action: the coordinator's CI push runs tests/test_install_update.py on macos-latest and macos-15-intel"
    },
    {
      "id": "R-RED-MAC",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "red",
      "status": "deferred",
      "command": [],
      "method": "A drill for the macOS root code (dropping the ownership check from _MACOS_ROOT) needs macOS to run its test.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "1200fcd98e6e8159f3891b614f3e0a06b53505416ad8ff3840ac84d454063dbc"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "fa2ce42898ee87f0e9d89385c00e5fe1e3a678fecdb91694423cb82708021291"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2c50df70a31c5ae2a7aab3ac72e998a1ab3abb4b891014afcdaf31f53f2cf81c"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "d3220231abc53fa831d8531ab81e24e46898d16d02dbe55f86a5687919f67126",
      "red": null,
      "reason": "macOS only; next action: run a drill replacing '! -user root -o -perm +022' with '-name nothing' on a macOS runner"
    },
    {
      "id": "R-MAN-AC10",
      "acceptance": [
        "AC-10"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Read winpipe's module and function docstrings against the code: they say what deliver, claim and client_is_me do, and claim no check that isn't made",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/review-ac10.md",
        "sha256": "4e0c0123ac0944be17ebf6528a9dcc171988369743596cfc5f7206cbcebdf304"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "b0bcbc335744ae3501f52b22c178d0337d2f312b6413c0c0e101f2ad2de71cde"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "da499e1348b1b2dceccc56a78d1b8c728c4653c9a26d0dad9a6b81a0f619637c",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-VERIFY-signature",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_a_tampered_list_is_refused",
        "tests/test_releasecheck.py::test_a_bad_signature_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-signature through tests/drills/run.py on a temporary copy: green, then 'if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):' replaced by 'if False:' in chatmon/releasecheck.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "636487654ad7e5e00ed3923113d62b94fdaff50e46ad830063efafde3643168e",
      "red": {
        "mutation": "chatmon/releasecheck.py: 'if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE Refused",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "792ed56338643cb3f8217a5ad6ff3ea449bda845cb57f9d98bb6d796ce2cb119"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-VERIFY-version",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_an_older_or_the_same_version_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-version through tests/drills/run.py on a temporary copy: green, then 'if version_key(version) <= version_key(installed):' replaced by 'if version_key(version) < version_key(installed):' in chatmon/releasecheck.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "636487654ad7e5e00ed3923113d62b94fdaff50e46ad830063efafde3643168e",
      "red": {
        "mutation": "chatmon/releasecheck.py: 'if version_key(version) <= version_key(installed):' -> 'if version_key(version) < version_key(installed):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_older_or_the_same_version_is_refused[9.0.0]",
        "observed_diagnostic": "_____________ test_an_older_or_the_same_version_is_refused[9.0.0] _____________",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "c0721393ffb4329adfddf0e2bc191adc64283eb317c0bfb244b19c0c5affd875"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-USER-handoff",
      "acceptance": [
        "AC-01-USER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_root_is_handed_the_signed_list_never_a_checksum"
      ],
      "method": "Red drill AC-01-USER-handoff through tests/drills/run.py on a temporary copy: green, then 'return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}' replaced by 'return PKEXEC, [HELPER, str(path), sha256(path) if path.exists() else \"0\" * 64], {}' in chatmon/updates.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "1200fcd98e6e8159f3891b614f3e0a06b53505416ad8ff3840ac84d454063dbc"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "fa2ce42898ee87f0e9d89385c00e5fe1e3a678fecdb91694423cb82708021291"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2c50df70a31c5ae2a7aab3ac72e998a1ab3abb4b891014afcdaf31f53f2cf81c"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "d3220231abc53fa831d8531ab81e24e46898d16d02dbe55f86a5687919f67126",
      "red": {
        "mutation": "chatmon/updates.py: 'return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}' -> 'return PKEXEC, [HELPER, str(path), sha256(path) if path.exists() else \"0\" * 64], {}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_root_is_handed_the_signed_list_never_a_checksum",
        "observed_diagnostic": "____________ test_root_is_handed_the_signed_list_never_a_checksum _____________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "e551832b7ffb7b7f4466e6fba914aad9cc9862c01be1e2fd6162c46caddd94cf"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-03-sqos",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_server_learns_who_you_are_but_can_never_act_as_you"
      ],
      "method": "Red drill AC-03-sqos through tests/drills/run.py on a temporary copy: green, then 'FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, None)' replaced by 'FILE_FLAG_OVERLAPPED, None)' in chatmon/winpipe.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "b0bcbc335744ae3501f52b22c178d0337d2f312b6413c0c0e101f2ad2de71cde"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "da499e1348b1b2dceccc56a78d1b8c728c4653c9a26d0dad9a6b81a0f619637c",
      "red": {
        "mutation": "chatmon/winpipe.py: 'FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, None)' -> 'FILE_FLAG_OVERLAPPED, None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [2] == [1]",
        "observed_diagnostic": "E       assert [2] == [1]",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "a5f877a5fca179167ed62969c3a8ca6e91c0a552e925d9f09707346cbdb60eab"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-03-owner",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_pipe_someone_else_serves_is_told_nothing"
      ],
      "method": "Red drill AC-03-owner through tests/drills/run.py on a temporary copy: green, then 'if not server_is_me(handle):' replaced by 'if False:' in chatmon/winpipe.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "b0bcbc335744ae3501f52b22c178d0337d2f312b6413c0c0e101f2ad2de71cde"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "da499e1348b1b2dceccc56a78d1b8c728c4653c9a26d0dad9a6b81a0f619637c",
      "red": {
        "mutation": "chatmon/winpipe.py: 'if not server_is_me(handle):' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_someone_else_serves_is_told_nothing",
        "observed_diagnostic": "_______________ test_a_pipe_someone_else_serves_is_told_nothing _______________",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "5993d54f2cc1ffd8de26c6cb87377fc643cf789dd909524ba2de265c47bb3197"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "55627d50aa56bd9f9305ee75e563f0e7567d29290588c574d55f4b1edede4c53"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-04-gate",
      "acceptance": [
        "AC-04"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_elevated_no_agents_command_line_ever_starts"
      ],
      "method": "Red drill AC-04-gate through tests/drills/run.py on a temporary copy: green, then 'root's rights (see elevated).\"\"\" if elevated():' replaced by 'root's rights (see elevated).\"\"\" if False:' in chatmon/agents.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "499c62447c5360041f201b80d52418608086780c5c6c485f61dd07ee42ec6df1"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        }
      ],
      "scope_sha256": "78b71f127ed10d53367aa76f210e90194bf83076267d90cac33355bf278f69a6",
      "red": {
        "mutation": "chatmon/agents.py: 'root\\'s rights (see elevated).\"\"\" if elevated():' -> 'root\\'s rights (see elevated).\"\"\" if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AgentError",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "835a978342b9966354a63ad3a1759328163146baac2f53b02733e79db5d0fe45"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-05-revocation-asked",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wintrust.py::test_revocation_is_asked_for_the_whole_chain"
      ],
      "method": "Red drill AC-05-revocation-asked through tests/drills/run.py on a temporary copy: green, then 'data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN' replaced by 'data.fdwRevocationChecks = WTD_REVOKE_NONE' in chatmon/wintrust.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "d49c6e14c022dc0add1a0fae02e649ac8ba0e8975c3cc0943753090399cc1b46",
      "red": {
        "mutation": "chatmon/wintrust.py: 'data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN' -> 'data.fdwRevocationChecks = WTD_REVOKE_NONE'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_revocation_is_asked_for_the_whole_chain",
        "observed_diagnostic": "________________ test_revocation_is_asked_for_the_whole_chain _________________",
        "before": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "2fb69a42a891715c92c5198f6cd478342857f9ecd15fb56387d23e77f2f8cece"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-05-try-later",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet"
      ],
      "method": "Red drill AC-05-try-later through tests/drills/run.py on a temporary copy: green, then 'if status == \"RevocationUnknown\":' replaced by 'if False:' in chatmon/updates.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "d49c6e14c022dc0add1a0fae02e649ac8ba0e8975c3cc0943753090399cc1b46",
      "red": {
        "mutation": "chatmon/updates.py: 'if status == \"RevocationUnknown\":' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet",
        "observed_diagnostic": "__ test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet ___",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a9391b944741d2ee7cca1e2e28ad862f0d8e12881a8936bb175c82b61fb6a47c"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-06-hold",
      "acceptance": [
        "AC-06"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_the_windows_installer_runs_from_a_copy_nobody_can_change"
      ],
      "method": "Red drill AC-06-hold through tests/drills/run.py on a temporary copy: green, then 'hold = wintrust.hold(copy)' replaced by 'hold = None' in chatmon/updates.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "d68b8b6fff71e0a61d99738c5a810b6d2633f1bdb32378f8186097ee76cbca88"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "b9d58ed0db8e6a6d8edf004f47d14e373e35f496b5325ecf96e962b10dc724d8",
      "red": {
        "mutation": "chatmon/updates.py: 'hold = wintrust.hold(copy)' -> 'hold = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_windows_installer_runs_from_a_copy_nobody_can_change",
        "observed_diagnostic": "________ test_the_windows_installer_runs_from_a_copy_nobody_can_change ________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "f8c7a013e1e299895327b4c799957c4d388eb017d405d8dba0309917849c2d08"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-07-prune",
      "acceptance": [
        "AC-07"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_backups_are_private_new_files_and_only_the_newest_five_are_kept"
      ],
      "method": "Red drill AC-07-prune through tests/drills/run.py on a temporary copy: green, then 'for *_, item in sorted(found)[:-BACKUPS_KEPT]:' replaced by 'for *_, item in sorted(found)[:0]:' in chatmon/agents.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        }
      ],
      "scope_sha256": "cc4a9cddcd801868c85fb480d396f7c559c12196244738e2d92cd60c8baa3d72",
      "red": {
        "mutation": "chatmon/agents.py: 'for *_, item in sorted(found)[:-BACKUPS_KEPT]:' -> 'for *_, item in sorted(found)[:0]:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_backups_are_private_new_files_and_only_the_newest_five_are_kept",
        "observed_diagnostic": "____ test_backups_are_private_new_files_and_only_the_newest_five_are_kept _____",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "916860b7dfa5f6cb6eb8e9cd4167c21cf300a7b249109189b5b28ecc6f5169cb"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-08-codex-top",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_codex_takes_a_config_with_arrays_inside_arrays",
        "tests/test_agents.py::test_codex_connect_then_disconnect_changes_nothing_but_notify"
      ],
      "method": "Red drill AC-08-codex-top through tests/drills/run.py on a temporary copy: green, then 'if item.strip() and not item.lstrip().startswith(\"#\")), len(lines))' replaced by 'if item.lstrip().startswith(\"[\")), len(lines))' in chatmon/agents.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        }
      ],
      "scope_sha256": "22a53b8ce78c73e2c561003c56593ec6dc358ca722c2ca55209a42bbd5e0cb4b",
      "red": {
        "mutation": "chatmon/agents.py: 'if item.strip() and not item.lstrip().startswith(\"#\")), len(lines))' -> 'if item.lstrip().startswith(\"[\")), len(lines))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Couldn't add the notify line cleanly",
        "observed_diagnostic": ">           raise AgentError(\"Couldn't add the notify line cleanly; not touching the file.\")",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "9b0ee6caf5e85c3eb6fd847204112fcb3fac472229207286c0b3c0e6fa9029ab"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-09-ORDER-swap",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_file_swapped_between_the_look_and_the_open_is_refused"
      ],
      "method": "Red drill AC-09-ORDER-swap through tests/drills/run.py on a temporary copy: green, then 'if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (looked.st_dev, looked.st_ino):' replaced by 'if not stat.S_ISREG(info.st_mode):' in chatmon/attachments.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "24dcc832a604f5ce15baf74f1e7abc9c5f8c272caf5925326a0169a612773b9a",
      "red": {
        "mutation": "chatmon/attachments.py: 'if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (looked.st_dev, looked.st_ino):' -> 'if not stat.S_ISREG(info.st_mode):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "9bd6a63b287d6d402edd9bb62e23e0adc29f3e3c539c0488ea7a592d4eb143bd"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-09-ORDER-look-first",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_folder_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-look-first through tests/drills/run.py on a temporary copy: green, then 'if not stat.S_ISREG(looked.st_mode):' replaced by 'if False:' in chatmon/attachments.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "24dcc832a604f5ce15baf74f1e7abc9c5f8c272caf5925326a0169a612773b9a",
      "red": {
        "mutation": "chatmon/attachments.py: 'if not stat.S_ISREG(looked.st_mode):' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_is_refused_without_being_opened",
        "observed_diagnostic": "________________ test_a_folder_is_refused_without_being_opened ________________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "e5f765c66dfdc1b251502ca8fcffbe5b606b33821664442aac74c42fe57a7b83"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-09-REMOTE-drive",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_windows_mapped_drives_are_refused_and_local_ones_taken"
      ],
      "method": "Red drill AC-09-REMOTE-drive through tests/drills/run.py on a temporary copy: green, then '_drive_type(drive + \"\\\\\") == DRIVE_REMOTE:' replaced by '_drive_type(drive + \"\\\\\") == -1:' in chatmon/attachments.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "24dcc832a604f5ce15baf74f1e7abc9c5f8c272caf5925326a0169a612773b9a",
      "red": {
        "mutation": "chatmon/attachments.py: '_drive_type(drive + \"\\\\\\\\\") == DRIVE_REMOTE:' -> '_drive_type(drive + \"\\\\\\\\\") == -1:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "d6df6ab4605db83d3b85a92132f1735b2e600046b6fff8b4de764bb6c8ee4e49"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-11-local",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_on_windows_everything_lives_on_this_computer"
      ],
      "method": "Red drill AC-11-local through tests/drills/run.py on a temporary copy: green, then 'if sys.platform == \"win32\": return _local()' replaced by 'if sys.platform == \"win32\": return _roaming()' in chatmon/paths.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "aa2ecf9a26761228152bfb2ec94b8bb01f4a865f7eee69b9e2a1b945d1b73422"
        }
      ],
      "scope_sha256": "d49a0f064a5b5c9ab2153dbdec19a652a868f8e4bac7f2ebb58489b17a3ef7c8",
      "red": {
        "mutation": "chatmon/paths.py: 'if sys.platform == \"win32\": return _local()' -> 'if sys.platform == \"win32\": return _roaming()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_everything_lives_on_this_computer",
        "observed_diagnostic": "______________ test_on_windows_everything_lives_on_this_computer ______________",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "5b206bc6cbf90530e0594bc76ac4bd2e3acd33bc187ea95d8b0d55308c002a4d"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-11-newer-wins",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_they_join_whats_on_this_computer_already_the_newer_file_winning"
      ],
      "method": "Red drill AC-11-newer-wins through tests/drills/run.py on a temporary copy: green, then 'if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:' replaced by 'if target.exists():' in chatmon/paths.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "aa2ecf9a26761228152bfb2ec94b8bb01f4a865f7eee69b9e2a1b945d1b73422"
        }
      ],
      "scope_sha256": "d49a0f064a5b5c9ab2153dbdec19a652a868f8e4bac7f2ebb58489b17a3ef7c8",
      "red": {
        "mutation": "chatmon/paths.py: 'if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:' -> 'if target.exists():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_they_join_whats_on_this_computer_already_the_newer_file_winning",
        "observed_diagnostic": "____ test_they_join_whats_on_this_computer_already_the_newer_file_winning _____",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "441f3595d38f85ed9101a79cd34e4cd9aa5bc22a6b77d993a53ea1969ef042e6"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "1427e80e866d5e82424292d689cc4f0ab6d9d3e7648481e56691749f16018442"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-12-kind",
      "acceptance": [
        "AC-12"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_chatmon_installed_by_the_system_says_which_package_manager"
      ],
      "method": "Red drill AC-12-kind through tests/drills/run.py on a temporary copy: green, then 'if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:' replaced by 'if subprocess.run(query, capture_output=True, timeout=10).returncode != 0:' in chatmon/updates.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "4406ff1e03cac14d2143bedbe95525e3636aa0fe60120118efcb3d6314aef722",
      "red": {
        "mutation": "chatmon/updates.py: 'if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:' -> 'if subprocess.run(query, capture_output=True, timeout=10).returncode != 0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chatmon_installed_by_the_system_says_which_package_manager",
        "observed_diagnostic": "______ test_a_chatmon_installed_by_the_system_says_which_package_manager ______",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "6f5443f0e70f2506cd3c452b82f25b3ce59548dd75fbcbab5f539b58e3624bfc"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-12-relaunch",
      "acceptance": [
        "AC-12"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_an_install_runs_root_side_then_relaunches_or_says_why"
      ],
      "method": "Red drill AC-12-relaunch through tests/drills/run.py on a temporary copy: green, then 'relaunch = relaunch_command(self.kind)' replaced by 'relaunch = None' in chatmon/updates.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "4406ff1e03cac14d2143bedbe95525e3636aa0fe60120118efcb3d6314aef722",
      "red": {
        "mutation": "chatmon/updates.py: 'relaunch = relaunch_command(self.kind)' -> 'relaunch = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_install_runs_root_side_then_relaunches_or_says_why[installed]",
        "observed_diagnostic": "____ test_an_install_runs_root_side_then_relaunches_or_says_why[installed] ____",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ac3a4c110aa7286b797ee388e07623bf75f2962fbf44050a4295866738e561ed"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-M6A-14-pin",
      "acceptance": [
        "AC-M6A-14"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill AC-M6A-14-pin through tests/drills/run.py on a temporary copy: green, then 'chatmon@v{v}' replaced by 'chatmon' in packaging/build.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills.log",
        "sha256": "fefc7b766cd7b9f4ba487a18dc10d6440553de6edb858338f17fbba4790bbe7e"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/build.py",
          "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "b77cafd3bba9681be0114fe01addf6c6849acf0cdf3a9b12c1e4011f1491c722",
      "red": {
        "mutation": "packaging/build.py: 'chatmon@v{v}' -> 'chatmon'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_release_notes_pin_the_pipx_install_to_the_release",
        "observed_diagnostic": "___________ test_release_notes_pin_the_pipx_install_to_the_release ____________",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "d5b8019be6b9fca946ed867a40c05ea1ae2cb338705116150b53ed1e81ccb846"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "ff874dd9e294d79bbe307bf9463eca4d55467018b6bb0201d300eca4463982f2"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-LINUX-launcher-owner",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_the_check_isnt_loaded_from_anything_but_roots_own"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-01-LINUX-launcher-owner through tests/drills/run.py on a temporary copy: green, then 'return info.st_uid == OWNER and not stat.S_ISLNK(info.st_mode) and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)' replaced by 'return True' in packaging/linux/verify-update made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "58fcab51bbb2d8f29b5df25588f1d604dc6797387f6afa5fdc3bbad0ae0660d6"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "a7913ed27c469832c2e517a9bce97f354a7c7782fa0efe0902d37c20bec49605",
      "red": {
        "mutation": "packaging/linux/verify-update: 'return info.st_uid == OWNER and not stat.S_ISLNK(info.st_mode) and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)' -> 'return True'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_check_isnt_loaded_from_anything_but_roots_own",
        "observed_diagnostic": "_ test_the_check_isnt_loaded_from_anything_but_roots_own[group-writable module] _",
        "before": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "f23b7b652b52021a1efc65db71b2f75c394455d0ee5ae2bd2ce0968bd88cde2a"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-LINUX-refusal-stops",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_tampered_list_is_refused_by_root",
        "tests/test_install_update.py::test_an_older_release_is_refused_by_root"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-01-LINUX-refusal-stops through tests/drills/run.py on a temporary copy: green, then '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || exit 3' replaced by '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || true' in packaging/linux/install-update made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "58fcab51bbb2d8f29b5df25588f1d604dc6797387f6afa5fdc3bbad0ae0660d6"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "a7913ed27c469832c2e517a9bce97f354a7c7782fa0efe0902d37c20bec49605",
      "red": {
        "mutation": "packaging/linux/install-update: '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || exit 3' -> '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || true'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_tampered_list_is_refused_by_root",
        "observed_diagnostic": "___________________ test_a_tampered_list_is_refused_by_root ____________________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "8001ce9859a03f6b2f7f802bcd7b7db74eb0ee919f36f5b2131766035f15069c"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-01-LINUX-installs-the-copy",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_signed_newer_package_is_installed_from_roots_own_copy"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-01-LINUX-installs-the-copy through tests/drills/run.py on a temporary copy: green, then 'apt-get install -y \"$dir/update.deb\"' replaced by 'apt-get install -y \"$file\"' in packaging/linux/install-update made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "9f19f92136b3f31d6582374e69fe12358c6b0512503cd5fb3caeea401bd1fc07"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "5dbb6e09f06f3da43d7c4e72ba3cef4329330d1d85927da3115c022de2dc41ca"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "58fcab51bbb2d8f29b5df25588f1d604dc6797387f6afa5fdc3bbad0ae0660d6"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "6b864284e5f755ebbfaef9458ac2376e89e1788e5c9f9a18a964b555daac88e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "e5d1860b4f8f798fd95a84d6c55d398ed681c26b4a02df2d5f4796d1687f710f"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "3d1749e1204a5ff57fa4c17949899f560dbf25b6659fe8ddf39c25e2bdec32d7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "f8c9554432722475e042eaa621782ddb4a0b9884aa556af9497d0ae03ff055fe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "cff87cbf81568f8b063e52efea8607a413f7234b1cb460894df23d7c99ed01a3"
        }
      ],
      "scope_sha256": "a7913ed27c469832c2e517a9bce97f354a7c7782fa0efe0902d37c20bec49605",
      "red": {
        "mutation": "packaging/linux/install-update: 'apt-get install -y \"$dir/update.deb\"' -> 'apt-get install -y \"$file\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_signed_newer_package_is_installed_from_roots_own_copy",
        "observed_diagnostic": "_________ test_a_signed_newer_package_is_installed_from_roots_own_copy _________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "5ab0c6db8c3c24fb83a45bd87206931f3e70af98523b5a4b5b034ccd8002d53f"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "733f48d83df4f0883a6a45939e9c21c692d79eedda97a20a465a66328ef4ac67"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-02-owner",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-02-owner through tests/drills/run.py on a temporary copy: green, then '[ \"$3\" = \"$OWNER\" ]' replaced by '[ -n \"$3\" ]' in packaging/macos/scripts/postinstall made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "e165ec117094172d9b67c064e990852fa4f16e17bfb7cf17c77da923b78a63e0",
      "red": {
        "mutation": "packaging/macos/scripts/postinstall: '[ \"$3\" = \"$OWNER\" ]' -> '[ -n \"$3\" ]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[someone else's]",
        "observed_diagnostic": "__________ test_a_folder_not_roots_alone_gets_nothing[someone else's] __________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "aa6892a51c9f78e6fd1bd32e290cb79df45914b8ae610f6223f599fbe5ef1d10"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-02-writable",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-02-writable through tests/drills/run.py on a temporary copy: green, then 'd????-??-*) ;;' replaced by 'd*) ;;' in packaging/macos/scripts/postinstall made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "e165ec117094172d9b67c064e990852fa4f16e17bfb7cf17c77da923b78a63e0",
      "red": {
        "mutation": "packaging/macos/scripts/postinstall: 'd????-??-*) ;;' -> 'd*) ;;'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[others can write]",
        "observed_diagnostic": "_________ test_a_folder_not_roots_alone_gets_nothing[others can write] _________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "9003afd8f52c522942229a199613ede78c3ee983153adb6c427aad68b9d8eaec"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-07-private",
      "acceptance": [
        "AC-07"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_backups_are_private_new_files_and_only_the_newest_five_are_kept"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-07-private through tests/drills/run.py on a temporary copy: green, then 'fd = os.open(copy, flags, 0o600)' replaced by 'fd = os.open(copy, flags, 0o644)' in chatmon/agents.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "36a5e02b752a37714be8440fc077f84557472bd13daa3ddf7c357703c5490020"
        }
      ],
      "scope_sha256": "cc4a9cddcd801868c85fb480d396f7c559c12196244738e2d92cd60c8baa3d72",
      "red": {
        "mutation": "chatmon/agents.py: 'fd = os.open(copy, flags, 0o600)' -> 'fd = os.open(copy, flags, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_backups_are_private_new_files_and_only_the_newest_five_are_kept",
        "observed_diagnostic": "_____ test_backups_are_private_new_files_and_only_the_newest_five_are_kept _____",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "35246572d7339b478fd7d0968d7ef1da3ec4b0d71c7d722b8a3cf106096bb57b"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "da8db9b327bbbc397bd337afe15c261fca6ea2ed6570adda3546c714cdf13a1b"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-09-REMOTE-linux",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_linux_network_and_fuse_mounts_are_refused_but_not_fuseblk"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-09-REMOTE-linux through tests/drills/run.py on a temporary copy: green, then 'kind = LINUX_REMOTE.get(_statfs_type(path) or 0)' replaced by 'kind = None' in chatmon/attachments.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "24dcc832a604f5ce15baf74f1e7abc9c5f8c272caf5925326a0169a612773b9a",
      "red": {
        "mutation": "chatmon/attachments.py: 'kind = LINUX_REMOTE.get(_statfs_type(path) or 0)' -> 'kind = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "d1ccadb5e05e91e4b74abe09620e5c6714e13b7e4466ce605b4be2c6ff4d587a"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "R-RED-AC-09-ORDER-pipe",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/tmp/m1a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_pipe_or_a_device_is_refused_without_being_opened"
      ],
      "method": "Run under WSL (Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2, Python 3.14.9, PyQt 6.11.0 in a private venv) on this Windows host. Red drill AC-09-ORDER-pipe through tests/drills/run.py on a temporary copy: green, then 'if not stat.S_ISREG(looked.st_mode):' replaced by 'if False:' in chatmon/attachments.py made the named tests fail as intended, then the original bytes restored (checked by SHA-256) and green again",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/drills-linux.log",
        "sha256": "48b1c9d36fa3eaa0927642dd7b887cac1e4be9343a0de9f23194b1d14c06c19c"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "24dcc832a604f5ce15baf74f1e7abc9c5f8c272caf5925326a0169a612773b9a",
      "red": {
        "mutation": "chatmon/attachments.py: 'if not stat.S_ISREG(looked.st_mode):' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_or_a_device_is_refused_without_being_opened",
        "observed_diagnostic": "___________ test_a_pipe_or_a_device_is_refused_without_being_opened ____________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "e5f765c66dfdc1b251502ca8fcffbe5b606b33821664442aac74c42fe57a7b83"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "461680add09637a5c835d8668ede91d454a39f450f4072e0fc683ae408f3217d"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-READY",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER",
        "AC-02",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-10",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review again at fb19cb9 (readiness.md): M1A-01 to M1A-12 and M6A-14 re-read against ASSESSMENT.md, the amended ROADMAP.md (the owner's security settings included) and pyproject.toml as they are now; no conflict or gap; the pending operations' outcomes and M7's use of client_is_me noted; AC-01-MACOS's drill needs a Mac.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/readiness.md",
        "sha256": "392c991b1eb872887216bb12e90ee39a723b75b9d689a7047a5cc7485188ae8c"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        }
      ],
      "scope_sha256": "e2176d6e7be9a22c33f32adae40a97237762cf323e9b2dc7bbcf28205be951bb",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-WINDOWS",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-USER",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on fb19cb9's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1241 passed, 148 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. AC-01-LINUX, AC-01-MACOS and AC-02 are left out: their tests are POSIX- or macOS-only and skip here (CI's and WSL's receipts cover them). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4/suite-windows.log",
        "sha256": "2d041d737c4983f9a73256c95d51463d4792262b3a54516e77e796950e87713b"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "b8409d9fcee4266d0af1d59b11bdff926a64dca21b5d8cad840ab9318c07ad66"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "1f0f96bc22e05c6976c9f2d9932740f40d01db1a5b33ab33f37c480347c2d405",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-MAN-AC10",
      "acceptance": [
        "AC-10"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Read winpipe's module and function docstrings again against the code at fb19cb9 (review-ac10.md): they say the DACL keeps other users out and describe client_is_me as a check a server can make on each connection, which app.py's accept path now makes (M7); nothing claims a check that isn't made.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/review-ac10.md",
        "sha256": "84a6f1faa07a20a2e687e364dd0fea9c444cce2d575a1a6b6dca519ff494c973"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "90bbdce055c10f31c01f14916fcda8eb489ce158079b69a9995a31af557407ba",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "red",
      "status": "deferred",
      "command": [],
      "method": "The drill for macOS's root code: in chatmon/updates.py's _MACOS_ROOT, replace '! -user root -o -perm +022' with '-name nothing', then tests/test_install_update.py::test_mac_an_app_others_could_change_is_never_run_as_root must fail, and pass again once the text is restored.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "b8409d9fcee4266d0af1d59b11bdff926a64dca21b5d8cad840ab9318c07ad66"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "9800670ce248931a8adb3994702f7f6f96744d63d3b4548801a3edc19260c5a5",
      "red": null,
      "reason": "Not run: the test needs macOS (ditto, BSD find, osascript). No Mac is here or in the test lab, and a CI run of a drill branch needs a push, which this worker may not make. Next action: Randy on a Mac, or the coordinator pushing a throwaway branch with the mutation and dispatching ci.yml on it; until then T-03-macos-root stays implemented."
    },
    {
      "id": "W4-BEH-CI-LINUX",
      "acceptance": [
        "AC-01-LINUX",
        "AC-02",
        "AC-07",
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632422",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job test (ubuntu-24.04, 3.15): every Linux test of these criteria passed. That is tests/test_install_update.py's root-side tests (a signed newer package installed from root's own copy; a tampered list, a bad signature, an older release and a changed package refused; a caller's checksum never taken; the check loaded only from root's own files), tests/test_packaging.py's postinstall tests (a folder not root's alone gets nothing), tests/test_agents.py's private backups, and tests/test_attachments.py's Linux mount and pipe tests. The same tests passed on ubuntu 3.11, ubuntu-24.04-arm 3.14 and the three distro containers. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132699632422-test-ubuntu-24.04-3.15.log",
        "sha256": "c8df7ed105a19cceca9f88adc79c3c24358bbdf3b6097f6c4f55b5d5e72de729"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "50767bf30a20ad7b19db2a2dc6ea8a50d8da434d5da1c98a08c36b4fe2d5635e",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-MACOS",
      "acceptance": [
        "AC-01-MACOS",
        "AC-02",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632411",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job test (macos-latest, 3.14): tests/test_install_update.py's macOS tests passed. They cover a signed newer package installed from a checked copy of Chatmon.app; a bad list, signature or older release refused; an app others could change never run as root; and the AppleScript handing paths over as data. Also passed: tests/test_packaging.py's postinstall tests under BSD ls and tests/test_attachments.py::test_mac_mounts_not_stored_here_are_refused (macOS statfs). The same tests passed on the 3.11 and 3.15 legs. This resolves the CI-MACOS pending operation. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132699632411-test-macos-latest-3.14.log",
        "sha256": "920bde71199ea9324e478253bf5cbbbe73ac6294ce31018d2e94db1ba7e91c04"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "b8409d9fcee4266d0af1d59b11bdff926a64dca21b5d8cad840ab9318c07ad66"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "eb2a3823ced4cda55d57b77ca47b74af1c3621f2c9d87e7aae63f50c9febbbdf",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-PKG-CONTAINERS",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677664360",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132701246294",
        "--log"
      ],
      "method": "Packages run 43677664360, the pull_request run on PR #18. Its head is fb19cb9, and its test merge with main (df72534) has fb19cb9's own tree, 5d0d6b2 (reports/wave4/ci/pr18-checks.txt), so it built exactly these files. Job linux. It built the deb and rpm, then installed each on a fresh system, ran it and removed it. In ubuntu:24.04, debian:trixie and fedora:44 containers it ran packaging/linux/test-install-update.sh, root's own update path with no caller's checksum. Each printed 'test-install-update: all good' (log lines 240, 268 and 822), and the job succeeded. This resolves the CI-CONTAINER pending operation. The earlier workflow_dispatch run 43675230966 on d3f6a6e (the same packaging/ and pyproject.toml) gave the same results; its logs are in reports/wave4/ci/ too. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkgpr-132701246294-linux.log",
        "sha256": "c57c818a86854b5485ef62ded369eea97879135c25bd2e0bf75e35406cf4962b"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "2a5be2948ceafdc5f0773604dc22c243ed8989de648b885b77a8120ff27c62d0",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-PKG-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677664360",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132701246370",
        "--log"
      ],
      "method": "Packages run 43677664360, the pull_request run on PR #18. Its head is fb19cb9, and its test merge with main (df72534) has fb19cb9's own tree, 5d0d6b2 (reports/wave4/ci/pr18-checks.txt), so it built exactly these files. Job macos (macos-latest). Chatmon.app was installed from the built .pkg. The job checked that it was owned by uid 0 and had Contents/Resources/install-update. Its own frozen verify-update refused files that aren't there with exit 3 (log line 491: 'The update wasn't installed: couldn't read missing.txt'). The macos-15-intel job did the same (pkgpr-132701246264-macos-macos-15-intel.log, line 582). The earlier workflow_dispatch run 43675230966 on d3f6a6e (the same packaging/ and pyproject.toml) gave the same results; its logs are in reports/wave4/ci/ too. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkgpr-132701246370-macos-macos-latest.log",
        "sha256": "9542fa04bf342bbffc3c0a8b5e734d9dedbd04ab7e17e83d7f0e987e3ca044b5"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "b8409d9fcee4266d0af1d59b11bdff926a64dca21b5d8cad840ab9318c07ad66"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "9800670ce248931a8adb3994702f7f6f96744d63d3b4548801a3edc19260c5a5",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-LINUX-installs-the-copy",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_signed_newer_package_is_installed_from_roots_own_copy"
      ],
      "method": "Red drill AC-01-LINUX-installs-the-copy in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "2a5be2948ceafdc5f0773604dc22c243ed8989de648b885b77a8120ff27c62d0",
      "red": {
        "mutation": "AC-01-LINUX-installs-the-copy: in packaging/linux/install-update, '    apt-get install -y \"$dir/update.deb\"' became '    apt-get install -y \"$file\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_signed_newer_package_is_installed_from_roots_own_copy",
        "observed_diagnostic": "_________ test_a_signed_newer_package_is_installed_from_roots_own_copy _________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "865132b13b559696bafc15ae2378d35d48a64053c5b3c634496e306dfd73390a"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-LINUX-launcher-owner",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_the_check_isnt_loaded_from_anything_but_roots_own"
      ],
      "method": "Red drill AC-01-LINUX-launcher-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "2a5be2948ceafdc5f0773604dc22c243ed8989de648b885b77a8120ff27c62d0",
      "red": {
        "mutation": "AC-01-LINUX-launcher-owner: in packaging/linux/verify-update, '    return info.st_uid == OWNER and not stat.S_ISLNK(info.st_mode) and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)' became '    return True'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_check_isnt_loaded_from_anything_but_roots_own",
        "observed_diagnostic": "_ test_the_check_isnt_loaded_from_anything_but_roots_own[group-writable module] _",
        "before": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "c4827c01ab14404cc4239f815b0bda683ed1d820a493f7effceb84ce26b40117"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-LINUX-refusal-stops",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_tampered_list_is_refused_by_root",
        "tests/test_install_update.py::test_an_older_release_is_refused_by_root"
      ],
      "method": "Red drill AC-01-LINUX-refusal-stops in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "2a5be2948ceafdc5f0773604dc22c243ed8989de648b885b77a8120ff27c62d0",
      "red": {
        "mutation": "AC-01-LINUX-refusal-stops: in packaging/linux/install-update, '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || exit 3' became '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || true'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_tampered_list_is_refused_by_root",
        "observed_diagnostic": "___________________ test_a_tampered_list_is_refused_by_root ____________________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "72d07c5aaef28531b053ec8e5396b9a5f0449f5c58b6754f0d2e4d9989187e56"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-USER-handoff",
      "acceptance": [
        "AC-01-USER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_root_is_handed_the_signed_list_never_a_checksum"
      ],
      "method": "Red drill AC-01-USER-handoff through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "b8409d9fcee4266d0af1d59b11bdff926a64dca21b5d8cad840ab9318c07ad66"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "9800670ce248931a8adb3994702f7f6f96744d63d3b4548801a3edc19260c5a5",
      "red": {
        "mutation": "AC-01-USER-handoff: in chatmon/updates.py, '        return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}' became '        return PKEXEC, [HELPER, str(path), sha256(path) if path.exists() else \"0\" * 64], {}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_root_is_handed_the_signed_list_never_a_checksum",
        "observed_diagnostic": "____________ test_root_is_handed_the_signed_list_never_a_checksum _____________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "933ec535938d5a207c38a9eab2c2040d06c9a05800617096954f77d4c868f510"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-VERIFY-signature",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_a_tampered_list_is_refused",
        "tests/test_releasecheck.py::test_a_bad_signature_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-signature through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "1e297b3cd0c5b812de025702cb378a69aaad6782af8176566452a699e1a56038",
      "red": {
        "mutation": "AC-01-VERIFY-signature: in chatmon/releasecheck.py, '    if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE Refused",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "650a004edd0e380adcab672c8017fe24c91779cd2a58991fe69aacbaf673fac0"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-01-VERIFY-version",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_an_older_or_the_same_version_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-version through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "1e297b3cd0c5b812de025702cb378a69aaad6782af8176566452a699e1a56038",
      "red": {
        "mutation": "AC-01-VERIFY-version: in chatmon/releasecheck.py, '    if version_key(version) <= version_key(installed):' became '    if version_key(version) < version_key(installed):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_older_or_the_same_version_is_refused[9.0.0]",
        "observed_diagnostic": "_____________ test_an_older_or_the_same_version_is_refused[9.0.0] _____________",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "b9b6887ef9672fce713a3d1335ee6924109e52cced7c1f59bc8c080f3a8cb8d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-02-owner",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "ccfed071e1318e19fe8f261f95d290a9ceaf87ef0aa5782c90314a2d31a444ab",
      "red": {
        "mutation": "AC-02-owner: in packaging/macos/scripts/postinstall, '    [ \"$3\" = \"$OWNER\" ]' became '    [ -n \"$3\" ]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[someone else's]",
        "observed_diagnostic": "__________ test_a_folder_not_roots_alone_gets_nothing[someone else's] __________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "aa6892a51c9f78e6fd1bd32e290cb79df45914b8ae610f6223f599fbe5ef1d10"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-02-writable",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-writable in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. The artifact is the harness's results record, whose observed line names the failing test; the red run's output tail in drills-linux.log begins after that line. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux-results.json",
        "sha256": "53609c1dab3ec1203a4064db3f278be00627393bb2fa64606fda10a331033fb4"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "ccfed071e1318e19fe8f261f95d290a9ceaf87ef0aa5782c90314a2d31a444ab",
      "red": {
        "mutation": "AC-02-writable: in packaging/macos/scripts/postinstall, '        d????-??-*) ;;' became '        d*) ;;'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[others can write]",
        "observed_diagnostic": "_________ test_a_folder_not_roots_alone_gets_nothing[others can write] _________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "9003afd8f52c522942229a199613ede78c3ee983153adb6c427aad68b9d8eaec"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-03-owner",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_pipe_someone_else_serves_is_told_nothing"
      ],
      "method": "Red drill AC-03-owner through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "90bbdce055c10f31c01f14916fcda8eb489ce158079b69a9995a31af557407ba",
      "red": {
        "mutation": "AC-03-owner: in chatmon/winpipe.py, '        if not server_is_me(handle):' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_someone_else_serves_is_told_nothing",
        "observed_diagnostic": "_______________ test_a_pipe_someone_else_serves_is_told_nothing _______________",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "3336526d1f73d58c3f011dcaa5b69622d5ee9859d1462b7c7b23f5d8003f160d"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-03-sqos",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_server_learns_who_you_are_but_can_never_act_as_you"
      ],
      "method": "Red drill AC-03-sqos through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "90bbdce055c10f31c01f14916fcda8eb489ce158079b69a9995a31af557407ba",
      "red": {
        "mutation": "AC-03-sqos: in chatmon/winpipe.py, '                             FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, None)' became '                             FILE_FLAG_OVERLAPPED, None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [2] == [1]",
        "observed_diagnostic": "E       assert [2] == [1]",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "66699332eb539426b08f0e08331fa30b1e627abc19b55d8320acdb69f9e6b168"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-04-gate",
      "acceptance": [
        "AC-04"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_elevated_no_agents_command_line_ever_starts"
      ],
      "method": "Red drill AC-04-gate through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "24a7f4e871555cc5a2d056f586cc16947acc49f11d594f5770790f6d12a98d34",
      "red": {
        "mutation": "AC-04-gate: in chatmon/agents.py, '    root\\'s rights (see elevated).\"\"\"\\n    if elevated():' became '    root\\'s rights (see elevated).\"\"\"\\n    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AgentError",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f01e4ff54243befe60f2594294576ecf9f20b52b161f9d15f47d91a14dc11a7f"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-05-revocation-asked",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wintrust.py::test_revocation_is_asked_for_the_whole_chain"
      ],
      "method": "Red drill AC-05-revocation-asked through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "28f74886aae5384f6deed0e304cc2968c328446c9b6e5e851aee272b9b38e733",
      "red": {
        "mutation": "AC-05-revocation-asked: in chatmon/wintrust.py, '    data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN' became '    data.fdwRevocationChecks = WTD_REVOKE_NONE'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_revocation_is_asked_for_the_whole_chain",
        "observed_diagnostic": "________________ test_revocation_is_asked_for_the_whole_chain _________________",
        "before": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "f4041715f6a13b70ee63a8eeec48135477c5f0dbf4423577e763fd75d1d547a6"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-05-try-later",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet"
      ],
      "method": "Red drill AC-05-try-later through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "28f74886aae5384f6deed0e304cc2968c328446c9b6e5e851aee272b9b38e733",
      "red": {
        "mutation": "AC-05-try-later: in chatmon/updates.py, '        if status == \"RevocationUnknown\":' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet",
        "observed_diagnostic": "__ test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet ___",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a76bcc36cc90568af506e3a43546754b4564df9cdbc2f32db208319da13d12e4"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-06-hold",
      "acceptance": [
        "AC-06"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_the_windows_installer_runs_from_a_copy_nobody_can_change"
      ],
      "method": "Red drill AC-06-hold through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "7fc489eea3bba9d0f7d6a2a515f678a0769fd86defa2d80d5c731c26c2146bff",
      "red": {
        "mutation": "AC-06-hold: in chatmon/updates.py, '            hold = wintrust.hold(copy)' became '            hold = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_windows_installer_runs_from_a_copy_nobody_can_change",
        "observed_diagnostic": "________ test_the_windows_installer_runs_from_a_copy_nobody_can_change ________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "9fb52ca2df320362d164380a4a598b1e64b12d0e3ef0004c6c29227c5eb9cee5"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-07-private",
      "acceptance": [
        "AC-07"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_backups_are_private_new_files_and_only_the_newest_five_are_kept"
      ],
      "method": "Red drill AC-07-private in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "26835113085e10b7a58b04abef1b05846173b44941b8944bed3a42333d5d442b",
      "red": {
        "mutation": "AC-07-private: in chatmon/agents.py, '            fd = os.open(copy, flags, 0o600)' became '            fd = os.open(copy, flags, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_backups_are_private_new_files_and_only_the_newest_five_are_kept",
        "observed_diagnostic": "_____ test_backups_are_private_new_files_and_only_the_newest_five_are_kept _____",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "b830663bbbade9395fd053da64f3dbf26c535b6bbc4dec39517be3a0307b864b"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-08-codex-top",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_codex_takes_a_config_with_arrays_inside_arrays",
        "tests/test_agents.py::test_codex_connect_then_disconnect_changes_nothing_but_notify"
      ],
      "method": "Red drill AC-08-codex-top through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "645280a6d729aadc1ff81b36c8027ba816f1a3e5265077b750518f390d1428d3",
      "red": {
        "mutation": "AC-08-codex-top: in chatmon/agents.py, 'if item.strip() and not item.lstrip().startswith(\"#\")), len(lines))' became 'if item.lstrip().startswith(\"[\")), len(lines))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Couldn't add the notify line cleanly",
        "observed_diagnostic": ">           raise AgentError(_(\"Couldn't add the notify line cleanly; not touching the file.\"))",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f0520784b203124c03789fc3672b2fec0d41e17dc77ede5c377fa66f2b9d9565"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-09-ORDER-look-first",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_folder_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-look-first through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "ccca26441f70c4312c896c9a9bb7c943e230903990d48f63acd65e67e9be20e6",
      "red": {
        "mutation": "AC-09-ORDER-look-first: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_is_refused_without_being_opened",
        "observed_diagnostic": "________________ test_a_folder_is_refused_without_being_opened ________________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-09-ORDER-pipe",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_pipe_or_a_device_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-pipe in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "ccca26441f70c4312c896c9a9bb7c943e230903990d48f63acd65e67e9be20e6",
      "red": {
        "mutation": "AC-09-ORDER-pipe: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_or_a_device_is_refused_without_being_opened",
        "observed_diagnostic": "___________ test_a_pipe_or_a_device_is_refused_without_being_opened ____________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-09-ORDER-swap",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_file_swapped_between_the_look_and_the_open_is_refused"
      ],
      "method": "Red drill AC-09-ORDER-swap through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "ccca26441f70c4312c896c9a9bb7c943e230903990d48f63acd65e67e9be20e6",
      "red": {
        "mutation": "AC-09-ORDER-swap: in chatmon/attachments.py, '    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (looked.st_dev, looked.st_ino):' became '    if not stat.S_ISREG(info.st_mode):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6f12e54660c08088c43c10940c35e681a28ac31294e95ef294161c671f0bcd6c"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-09-REMOTE-drive",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_windows_mapped_drives_are_refused_and_local_ones_taken"
      ],
      "method": "Red drill AC-09-REMOTE-drive through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "ccca26441f70c4312c896c9a9bb7c943e230903990d48f63acd65e67e9be20e6",
      "red": {
        "mutation": "AC-09-REMOTE-drive: in chatmon/attachments.py, '_drive_type(drive + \"\\\\\\\\\") == DRIVE_REMOTE:' became '_drive_type(drive + \"\\\\\\\\\") == -1:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "cbd6221fbdc789cac84f5ffd15eb3f1134e06bc0ce2accb38e53318a0636faf8"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-09-REMOTE-linux",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_linux_network_and_fuse_mounts_are_refused_but_not_fuseblk"
      ],
      "method": "Red drill AC-09-REMOTE-linux in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills-linux.log",
        "sha256": "5091b8d5bfecd45e4a2db043178824566eb85943baddc0fb1dff8a98df2fc685"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "ccca26441f70c4312c896c9a9bb7c943e230903990d48f63acd65e67e9be20e6",
      "red": {
        "mutation": "AC-09-REMOTE-linux: in chatmon/attachments.py, '            kind = LINUX_REMOTE.get(_statfs_type(path) or 0)' became '            kind = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "f54f8d13d71363b7ff5700601047dc3da665806d32f41d36768eb8ca55cfc4ee"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-11-local",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_on_windows_everything_lives_on_this_computer"
      ],
      "method": "Red drill AC-11-local through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "00c83041a3d2a0dfc972ccba1166c28b2d6375f95ddf5c97980efb91b1a87cbc",
      "red": {
        "mutation": "AC-11-local: in chatmon/paths.py, '    if sys.platform == \"win32\":\\n        return _local()' became '    if sys.platform == \"win32\":\\n        return _roaming()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_everything_lives_on_this_computer",
        "observed_diagnostic": "______________ test_on_windows_everything_lives_on_this_computer ______________",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "df7ca4abfa4b50f5a879ce535095332b45941528be6d7009f17e1e656037a544"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-11-newer-wins",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_they_join_whats_on_this_computer_already_the_newer_file_winning"
      ],
      "method": "Red drill AC-11-newer-wins through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "00c83041a3d2a0dfc972ccba1166c28b2d6375f95ddf5c97980efb91b1a87cbc",
      "red": {
        "mutation": "AC-11-newer-wins: in chatmon/paths.py, '            if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:' became '            if target.exists():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_they_join_whats_on_this_computer_already_the_newer_file_winning",
        "observed_diagnostic": "____ test_they_join_whats_on_this_computer_already_the_newer_file_winning _____",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "dff1698ecf0d9224354e91cab1608669cc096f88ab521fda98c5565e21a61f74"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-12-kind",
      "acceptance": [
        "AC-12"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_chatmon_installed_by_the_system_says_which_package_manager"
      ],
      "method": "Red drill AC-12-kind through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "5f4711dbd0ff4a4e593d292bbca884483e5a9de62aaba47d93c5c2da53f198b2",
      "red": {
        "mutation": "AC-12-kind: in chatmon/updates.py, '                    if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:' became '                    if subprocess.run(query, capture_output=True, timeout=10).returncode != 0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chatmon_installed_by_the_system_says_which_package_manager",
        "observed_diagnostic": "______ test_a_chatmon_installed_by_the_system_says_which_package_manager ______",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "e836a82eecb9e14e69b92a31e507ff021ee3c299c89c1ec8434e380b628cbc01"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "ca878f84f5df93bb338d03fdc065c213a2ff8f4ff2a21f59afdde2a6f0c45e82"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-AC-M6A-14-pin",
      "acceptance": [
        "AC-M6A-14"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill AC-M6A-14-pin through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4/drills.log",
        "sha256": "1d3293596875bba0499be358859d8a9ad0e25f49c3e4d3fb348317dce428ee54"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "e1896d3574b55780f8d8179e24ab3192969d83c9f58611caec9666e939c0af2f"
        }
      ],
      "scope_sha256": "27baa0889d68b00bf72ed2046325136e44ff8a6feef6217a5f9bd468351c4853",
      "red": {
        "mutation": "AC-M6A-14-pin: in packaging/build.py, 'chatmon@v{v}' became 'chatmon'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_release_notes_pin_the_pipx_install_to_the_release",
        "observed_diagnostic": "___________ test_release_notes_pin_the_pipx_install_to_the_release ____________",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "bb95eb8b33545c099e1cea85fa3d9ff100f0607a698c76a6cd89edb3e416df8d"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3bf3a74f9c63e0ce6601d26d4106adfc5095dcbb1113ee49744d6a7c987457ad"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-READY",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER",
        "AC-02",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-10",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review, round two, at bf9d8ac (readiness.md): M1A-01 to M1A-12 and M6A-14 re-read against ASSESSMENT.md, the amended ROADMAP.md and pyproject.toml as they are now; no conflict or gap; AC-01-MACOS's red drill still needs a Mac.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/readiness.md",
        "sha256": "34b1ca09ddcde03343c49c27f1eb76bc73929bbf2eb7b4a26261a4f10177c570"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        }
      ],
      "scope_sha256": "94035a8c01be5a8609c79defc0175c61040444a78fd78c76488287aa8260d2e4",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-BEH-WINDOWS",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-USER",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on bf9d8ac's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1256 passed, 178 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. AC-01-LINUX, AC-01-MACOS and AC-02 are left out: their tests are POSIX- or macOS-only and skip here (CI's and WSL's receipts cover them). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4b/suite-windows.log",
        "sha256": "7f503b5d1a475b727e01e7b972cf58f5c756082c5dabfdcb6be93c57621c00ad"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "f2884bb278b3f95f9b37134cf6188ba0e6ef0e83a7f8f260c9068df7ce15aca7",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-MAN-AC10",
      "acceptance": [
        "AC-10"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Read winpipe's module and function docstrings again against the code at bf9d8ac (review-ac10.md): they say the DACL keeps other users out and describe client_is_me as a check a server can make on each connection, which app.py's accept path now makes (M7); nothing claims a check that isn't made.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/review-ac10.md",
        "sha256": "9de7110657ca576f0da434a8f339e24f5e145931f945501cfa30d88ac23a0df0"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "ea9df81c50c2abd28ee7d70c311001705f195a03af799aafde2ab3311c65e459",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "red",
      "status": "deferred",
      "command": [],
      "method": "The drill for macOS's root code: in chatmon/updates.py's _MACOS_ROOT, replace '! -user root -o -perm +022' with '-name nothing', then tests/test_install_update.py::test_mac_an_app_others_could_change_is_never_run_as_root must fail, and pass again once the text is restored.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "11091cdd7020d1280c42a73cad0466b011e1539b2b37dfc49066d8d3a671e6f4",
      "red": null,
      "reason": "Not run: the test needs macOS (ditto, BSD find, osascript). No Mac is here or in the test lab, and a CI run of a drill branch needs a push, which this worker may not make. Next action: Randy on a Mac, or the coordinator pushing a throwaway branch with the mutation and dispatching ci.yml on it; until then T-03-macos-root stays implemented."
    },
    {
      "id": "W4B-BEH-CI-LINUX",
      "acceptance": [
        "AC-01-LINUX",
        "AC-02",
        "AC-07",
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560297",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job test (ubuntu-24.04, 3.15): every Linux test of these criteria passed. That is tests/test_install_update.py's root-side tests (a signed newer package installed from root's own copy; a tampered list, a bad signature, an older release and a changed package refused; a caller's checksum never taken; the check loaded only from root's own files), tests/test_packaging.py's postinstall tests (a folder not root's alone gets nothing), tests/test_agents.py's private backups, and tests/test_attachments.py's Linux mount and pipe tests. The same tests passed on ubuntu 3.11, ubuntu-24.04-arm 3.14 and the three distro containers. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto bf9d8ac's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-bf9d8ac.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132773560297-test-ubuntu-24.04-3.15.log",
        "sha256": "365e319b53a88e4ac0668fb8af697a801a6334b65195a144a40eecdc2916dadc"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "fb59b7b4f529f676f2124f0f066a420272858c846322a72b580a21f4dd5e16cc",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-BEH-CI-MACOS",
      "acceptance": [
        "AC-01-MACOS",
        "AC-02",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560342",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job test (macos-latest, 3.14): tests/test_install_update.py's macOS tests passed. They cover a signed newer package installed from a checked copy of Chatmon.app; a bad list, signature or older release refused; an app others could change never run as root; and the AppleScript handing paths over as data. Also passed: tests/test_packaging.py's postinstall tests under BSD ls and tests/test_attachments.py::test_mac_mounts_not_stored_here_are_refused (macOS statfs). The same tests passed on the 3.11 and 3.15 legs. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto bf9d8ac's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-bf9d8ac.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132773560342-test-macos-latest-3.14.log",
        "sha256": "a1e97fcbcd11b0d99311b71ae95f232afaae0c5fc2f82fd7b711eb7f69580a34"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "a2fbe7d7a755ea7276704563560d57f3727f20cafe45c72fcc2db47be8951c8d",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-BEH-PKG-CONTAINERS",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43701523037",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773549513",
        "--log"
      ],
      "method": "Packages run 43701523037, the pull_request run on PR #18 at bf9d8ac, whose test merge has bf9d8ac's own tree (reports/wave4b/ci: the merge's tree equals bf9d8ac's). Job linux. It built the deb and rpm, then installed each on a fresh system, ran it and removed it. In ubuntu:24.04, debian:trixie and fedora:44 containers it ran packaging/linux/test-install-update.sh, root's own update path with no caller's checksum. Each printed 'test-install-update: all good' (log lines 240, 269 and 823), and the job succeeded. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkg-132773549513-linux.log",
        "sha256": "81497b8f6f89aeb0b7cd8f3291c09a9bb4dbcf032695186b84b87008c54380ed"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e85c850b852794307bb881ce13fb23da4b2ef426a060a3a38599fa358eca32d0",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-BEH-PKG-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43701523037",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773549569",
        "--log"
      ],
      "method": "Packages run 43701523037, the pull_request run on PR #18 at bf9d8ac, whose test merge has bf9d8ac's own tree (reports/wave4b/ci: the merge's tree equals bf9d8ac's). Job macos (macos-latest). Chatmon.app was installed from the built .pkg. The job checked that it was owned by uid 0 and had Contents/Resources/install-update. Its own frozen verify-update refused files that aren't there with exit 3 (log line 491: 'The update wasn't installed: couldn't read missing.txt'). The macos-15-intel job did the same (pkg-132773549510-macos-macos-15-intel.log, line 495). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkg-132773549569-macos-macos-latest.log",
        "sha256": "160b3a156fb6420a2479e582d22a6d77f83338366d66dc309848d916b8a929ab"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "11091cdd7020d1280c42a73cad0466b011e1539b2b37dfc49066d8d3a671e6f4",
      "red": null,
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-LINUX-installs-the-copy",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_signed_newer_package_is_installed_from_roots_own_copy"
      ],
      "method": "Red drill AC-01-LINUX-installs-the-copy in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e85c850b852794307bb881ce13fb23da4b2ef426a060a3a38599fa358eca32d0",
      "red": {
        "mutation": "AC-01-LINUX-installs-the-copy: in packaging/linux/install-update, '    apt-get install -y \"$dir/update.deb\"' became '    apt-get install -y \"$file\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_signed_newer_package_is_installed_from_roots_own_copy",
        "observed_diagnostic": "_________ test_a_signed_newer_package_is_installed_from_roots_own_copy _________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "865132b13b559696bafc15ae2378d35d48a64053c5b3c634496e306dfd73390a"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-LINUX-launcher-owner",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_the_check_isnt_loaded_from_anything_but_roots_own"
      ],
      "method": "Red drill AC-01-LINUX-launcher-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e85c850b852794307bb881ce13fb23da4b2ef426a060a3a38599fa358eca32d0",
      "red": {
        "mutation": "AC-01-LINUX-launcher-owner: in packaging/linux/verify-update, '    return info.st_uid == OWNER and not stat.S_ISLNK(info.st_mode) and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)' became '    return True'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_check_isnt_loaded_from_anything_but_roots_own",
        "observed_diagnostic": "_ test_the_check_isnt_loaded_from_anything_but_roots_own[group-writable module] _",
        "before": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "c4827c01ab14404cc4239f815b0bda683ed1d820a493f7effceb84ce26b40117"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-LINUX-refusal-stops",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_tampered_list_is_refused_by_root",
        "tests/test_install_update.py::test_an_older_release_is_refused_by_root"
      ],
      "method": "Red drill AC-01-LINUX-refusal-stops in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e85c850b852794307bb881ce13fb23da4b2ef426a060a3a38599fa358eca32d0",
      "red": {
        "mutation": "AC-01-LINUX-refusal-stops: in packaging/linux/install-update, '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || exit 3' became '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || true'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_tampered_list_is_refused_by_root",
        "observed_diagnostic": "___________________ test_a_tampered_list_is_refused_by_root ____________________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "72d07c5aaef28531b053ec8e5396b9a5f0449f5c58b6754f0d2e4d9989187e56"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-USER-handoff",
      "acceptance": [
        "AC-01-USER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_root_is_handed_the_signed_list_never_a_checksum"
      ],
      "method": "Red drill AC-01-USER-handoff through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "11091cdd7020d1280c42a73cad0466b011e1539b2b37dfc49066d8d3a671e6f4",
      "red": {
        "mutation": "AC-01-USER-handoff: in chatmon/updates.py, '        return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}' became '        return PKEXEC, [HELPER, str(path), sha256(path) if path.exists() else \"0\" * 64], {}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_root_is_handed_the_signed_list_never_a_checksum",
        "observed_diagnostic": "____________ test_root_is_handed_the_signed_list_never_a_checksum _____________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "3f8fb0a17c5dcf0e8ae671cc836c6746331846bd125f81ef21c02ac22bfdd01f"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-VERIFY-signature",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_a_tampered_list_is_refused",
        "tests/test_releasecheck.py::test_a_bad_signature_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-signature through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e1cefe2d42474c773684768213f0ce55255628eaaadf53cccbf609022e3005a4",
      "red": {
        "mutation": "AC-01-VERIFY-signature: in chatmon/releasecheck.py, '    if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE Refused",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "650a004edd0e380adcab672c8017fe24c91779cd2a58991fe69aacbaf673fac0"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-01-VERIFY-version",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_an_older_or_the_same_version_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-version through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "e1cefe2d42474c773684768213f0ce55255628eaaadf53cccbf609022e3005a4",
      "red": {
        "mutation": "AC-01-VERIFY-version: in chatmon/releasecheck.py, '    if version_key(version) <= version_key(installed):' became '    if version_key(version) < version_key(installed):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_older_or_the_same_version_is_refused[9.0.0]",
        "observed_diagnostic": "_____________ test_an_older_or_the_same_version_is_refused[9.0.0] _____________",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "b9b6887ef9672fce713a3d1335ee6924109e52cced7c1f59bc8c080f3a8cb8d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-02-owner",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "ff44ab48852f437ed106f6d374973064725b052adfd96becec3293da6ed535b8",
      "red": {
        "mutation": "AC-02-owner: in packaging/macos/scripts/postinstall, '    [ \"$3\" = \"$OWNER\" ]' became '    [ -n \"$3\" ]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[someone else's]",
        "observed_diagnostic": "__________ test_a_folder_not_roots_alone_gets_nothing[someone else's] __________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "aa6892a51c9f78e6fd1bd32e290cb79df45914b8ae610f6223f599fbe5ef1d10"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-02-writable",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-writable in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. The artifact is the harness's results record, whose observed line names the failing test; the red run's output tail in drills-linux.log begins after that line. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux-results.json",
        "sha256": "53609c1dab3ec1203a4064db3f278be00627393bb2fa64606fda10a331033fb4"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "ff44ab48852f437ed106f6d374973064725b052adfd96becec3293da6ed535b8",
      "red": {
        "mutation": "AC-02-writable: in packaging/macos/scripts/postinstall, '        d????-??-*) ;;' became '        d*) ;;'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[others can write]",
        "observed_diagnostic": "_________ test_a_folder_not_roots_alone_gets_nothing[others can write] _________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "9003afd8f52c522942229a199613ede78c3ee983153adb6c427aad68b9d8eaec"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-03-owner",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_pipe_someone_else_serves_is_told_nothing"
      ],
      "method": "Red drill AC-03-owner through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "ea9df81c50c2abd28ee7d70c311001705f195a03af799aafde2ab3311c65e459",
      "red": {
        "mutation": "AC-03-owner: in chatmon/winpipe.py, '        if not server_is_me(handle):' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_someone_else_serves_is_told_nothing",
        "observed_diagnostic": "_______________ test_a_pipe_someone_else_serves_is_told_nothing _______________",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "3336526d1f73d58c3f011dcaa5b69622d5ee9859d1462b7c7b23f5d8003f160d"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-03-sqos",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_server_learns_who_you_are_but_can_never_act_as_you"
      ],
      "method": "Red drill AC-03-sqos through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "ea9df81c50c2abd28ee7d70c311001705f195a03af799aafde2ab3311c65e459",
      "red": {
        "mutation": "AC-03-sqos: in chatmon/winpipe.py, '                             FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, None)' became '                             FILE_FLAG_OVERLAPPED, None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [2] == [1]",
        "observed_diagnostic": "E       assert [2] == [1]",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "66699332eb539426b08f0e08331fa30b1e627abc19b55d8320acdb69f9e6b168"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-04-gate",
      "acceptance": [
        "AC-04"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_elevated_no_agents_command_line_ever_starts"
      ],
      "method": "Red drill AC-04-gate through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "bec27d26c62a08a6fa0d6e7c30d4e68d19c4f275dec0d5579feda87f33c167d7",
      "red": {
        "mutation": "AC-04-gate: in chatmon/agents.py, '    root\\'s rights (see elevated).\"\"\"\\n    if elevated():' became '    root\\'s rights (see elevated).\"\"\"\\n    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AgentError",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f01e4ff54243befe60f2594294576ecf9f20b52b161f9d15f47d91a14dc11a7f"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-05-revocation-asked",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wintrust.py::test_revocation_is_asked_for_the_whole_chain"
      ],
      "method": "Red drill AC-05-revocation-asked through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "30b663ae930a9db2d6549d8513a0ddd0d4064835e1f519180672c7dd30ae5728",
      "red": {
        "mutation": "AC-05-revocation-asked: in chatmon/wintrust.py, '    data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN' became '    data.fdwRevocationChecks = WTD_REVOKE_NONE'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_revocation_is_asked_for_the_whole_chain",
        "observed_diagnostic": "________________ test_revocation_is_asked_for_the_whole_chain _________________",
        "before": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "f4041715f6a13b70ee63a8eeec48135477c5f0dbf4423577e763fd75d1d547a6"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-05-try-later",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet"
      ],
      "method": "Red drill AC-05-try-later through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "30b663ae930a9db2d6549d8513a0ddd0d4064835e1f519180672c7dd30ae5728",
      "red": {
        "mutation": "AC-05-try-later: in chatmon/updates.py, '        if status == \"RevocationUnknown\":' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet",
        "observed_diagnostic": "__ test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet ___",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "e19238a7670e2352a0be1d6e9cd215cc980929e81b05de5ead0b588fe3b7f953"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-06-hold",
      "acceptance": [
        "AC-06"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_the_windows_installer_runs_from_a_copy_nobody_can_change"
      ],
      "method": "Red drill AC-06-hold through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "a5cb75fd755ef9c6fbe3f8820b8f3533633b7eabfb35e90e773e11529f77aa40",
      "red": {
        "mutation": "AC-06-hold: in chatmon/updates.py, '            hold = wintrust.hold(copy)' became '            hold = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_windows_installer_runs_from_a_copy_nobody_can_change",
        "observed_diagnostic": "________ test_the_windows_installer_runs_from_a_copy_nobody_can_change ________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "0e0dbcacd08ab833223f46c0b3a5dfc535338b509ac023017fc81618ce2ccb67"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-07-private",
      "acceptance": [
        "AC-07"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_backups_are_private_new_files_and_only_the_newest_five_are_kept"
      ],
      "method": "Red drill AC-07-private in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "a3b26b6d489188522caac0c8e6dad32bc70829cc135bcc4328d37dc14db39e58",
      "red": {
        "mutation": "AC-07-private: in chatmon/agents.py, '            fd = os.open(copy, flags, 0o600)' became '            fd = os.open(copy, flags, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_backups_are_private_new_files_and_only_the_newest_five_are_kept",
        "observed_diagnostic": "_____ test_backups_are_private_new_files_and_only_the_newest_five_are_kept _____",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "b830663bbbade9395fd053da64f3dbf26c535b6bbc4dec39517be3a0307b864b"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-08-codex-top",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_codex_takes_a_config_with_arrays_inside_arrays",
        "tests/test_agents.py::test_codex_connect_then_disconnect_changes_nothing_but_notify"
      ],
      "method": "Red drill AC-08-codex-top through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "e1a6ad7c8f7e7ac3bc3fc1482a639db2c526c91b9fda3205fd1ec5ae99f9f2c6",
      "red": {
        "mutation": "AC-08-codex-top: in chatmon/agents.py, 'if item.strip() and not item.lstrip().startswith(\"#\")), len(lines))' became 'if item.lstrip().startswith(\"[\")), len(lines))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Couldn't add the notify line cleanly",
        "observed_diagnostic": ">           raise AgentError(_(\"Couldn't add the notify line cleanly; not touching the file.\"))",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f0520784b203124c03789fc3672b2fec0d41e17dc77ede5c377fa66f2b9d9565"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-09-ORDER-look-first",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_folder_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-look-first through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "18bab36dcc6e0077939a9fafad3a0a5f6076f1e4a5eaf0b740e0cb5b2f46e977",
      "red": {
        "mutation": "AC-09-ORDER-look-first: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_is_refused_without_being_opened",
        "observed_diagnostic": "________________ test_a_folder_is_refused_without_being_opened ________________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-09-ORDER-pipe",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_pipe_or_a_device_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-pipe in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "18bab36dcc6e0077939a9fafad3a0a5f6076f1e4a5eaf0b740e0cb5b2f46e977",
      "red": {
        "mutation": "AC-09-ORDER-pipe: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_or_a_device_is_refused_without_being_opened",
        "observed_diagnostic": "___________ test_a_pipe_or_a_device_is_refused_without_being_opened ____________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-09-ORDER-swap",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_file_swapped_between_the_look_and_the_open_is_refused"
      ],
      "method": "Red drill AC-09-ORDER-swap through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "18bab36dcc6e0077939a9fafad3a0a5f6076f1e4a5eaf0b740e0cb5b2f46e977",
      "red": {
        "mutation": "AC-09-ORDER-swap: in chatmon/attachments.py, '    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (looked.st_dev, looked.st_ino):' became '    if not stat.S_ISREG(info.st_mode):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6f12e54660c08088c43c10940c35e681a28ac31294e95ef294161c671f0bcd6c"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-09-REMOTE-drive",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_windows_mapped_drives_are_refused_and_local_ones_taken"
      ],
      "method": "Red drill AC-09-REMOTE-drive through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "18bab36dcc6e0077939a9fafad3a0a5f6076f1e4a5eaf0b740e0cb5b2f46e977",
      "red": {
        "mutation": "AC-09-REMOTE-drive: in chatmon/attachments.py, '_drive_type(drive + \"\\\\\\\\\") == DRIVE_REMOTE:' became '_drive_type(drive + \"\\\\\\\\\") == -1:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "cbd6221fbdc789cac84f5ffd15eb3f1134e06bc0ce2accb38e53318a0636faf8"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-09-REMOTE-linux",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_linux_network_and_fuse_mounts_are_refused_but_not_fuseblk"
      ],
      "method": "Red drill AC-09-REMOTE-linux in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills-linux.log",
        "sha256": "7fc4830d5984b48a5777dbb12c66904bef036971885028d15b1c118f24cc06a0"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "18bab36dcc6e0077939a9fafad3a0a5f6076f1e4a5eaf0b740e0cb5b2f46e977",
      "red": {
        "mutation": "AC-09-REMOTE-linux: in chatmon/attachments.py, '            kind = LINUX_REMOTE.get(_statfs_type(path) or 0)' became '            kind = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "f54f8d13d71363b7ff5700601047dc3da665806d32f41d36768eb8ca55cfc4ee"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-11-local",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_on_windows_everything_lives_on_this_computer"
      ],
      "method": "Red drill AC-11-local through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "1f8fea8d0976c2273e1a45e65e730ea839086f8de9265e237882543744915add",
      "red": {
        "mutation": "AC-11-local: in chatmon/paths.py, '    if sys.platform == \"win32\":\\n        return _local()' became '    if sys.platform == \"win32\":\\n        return _roaming()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_everything_lives_on_this_computer",
        "observed_diagnostic": "______________ test_on_windows_everything_lives_on_this_computer ______________",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "df7ca4abfa4b50f5a879ce535095332b45941528be6d7009f17e1e656037a544"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-11-newer-wins",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_they_join_whats_on_this_computer_already_the_newer_file_winning"
      ],
      "method": "Red drill AC-11-newer-wins through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "1f8fea8d0976c2273e1a45e65e730ea839086f8de9265e237882543744915add",
      "red": {
        "mutation": "AC-11-newer-wins: in chatmon/paths.py, '            if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:' became '            if target.exists():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_they_join_whats_on_this_computer_already_the_newer_file_winning",
        "observed_diagnostic": "____ test_they_join_whats_on_this_computer_already_the_newer_file_winning _____",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "dff1698ecf0d9224354e91cab1608669cc096f88ab521fda98c5565e21a61f74"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-12-kind",
      "acceptance": [
        "AC-12"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_chatmon_installed_by_the_system_says_which_package_manager"
      ],
      "method": "Red drill AC-12-kind through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "8b0524a66d0adc99919266bfee9121d6f6c6f9a176ee27cf3328e4b6deb8bedb",
      "red": {
        "mutation": "AC-12-kind: in chatmon/updates.py, '                    if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:' became '                    if subprocess.run(query, capture_output=True, timeout=10).returncode != 0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chatmon_installed_by_the_system_says_which_package_manager",
        "observed_diagnostic": "______ test_a_chatmon_installed_by_the_system_says_which_package_manager ______",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "91c8bbd8b7b7c6ec1470e8fcc0ecba1bfa6559fa10dc8806a103ac9b32f2de63"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-RED-AC-M6A-14-pin",
      "acceptance": [
        "AC-M6A-14"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill AC-M6A-14-pin through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4b/drills.log",
        "sha256": "4c25e7581d80c57fa1ce7a51a152b977dc5cc3612fc5493569f744b377fb1aa1"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "ec31974bb57df962865f7e7eed268d8ff69514d3ba1e85f05d6c7f0c3c8c171f",
      "red": {
        "mutation": "AC-M6A-14-pin: in packaging/build.py, 'chatmon@v{v}' became 'chatmon'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_release_notes_pin_the_pipx_install_to_the_release",
        "observed_diagnostic": "___________ test_release_notes_pin_the_pipx_install_to_the_release ____________",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "7373e5c1acdedf29e61c52bf3f180b0c0ef0144bf16a08ee8f81d3f2081d7e67"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
          }
        ]
      },
      "reason": "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4C-READY",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-LINUX",
        "AC-01-MACOS",
        "AC-01-USER",
        "AC-02",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-10",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review, round three, at 3586a0d (readiness.md): M1A-01 to M1A-12 and M6A-14 re-read against ASSESSMENT.md, the amended ROADMAP.md and pyproject.toml as they are now; no conflict or gap; AC-01-MACOS's red drill still needs a Mac.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/readiness.md",
        "sha256": "2d5e5390b23d32c0154e8bf45c82e8d342adbb82dd13da6f7d3cda2b9d69a9bf"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        }
      ],
      "scope_sha256": "11ac51dc1fdf187e842ab294105317fc37e732493f6b898052fdc41a9fae9c6d",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-BEH-WINDOWS",
      "acceptance": [
        "AC-01-VERIFY",
        "AC-01-USER",
        "AC-03",
        "AC-04",
        "AC-05",
        "AC-06",
        "AC-07",
        "AC-08",
        "AC-09-ORDER",
        "AC-09-REMOTE",
        "AC-11",
        "AC-12",
        "AC-M6A-14"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on 3586a0d's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1259 passed, 178 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. AC-01-LINUX, AC-01-MACOS and AC-02 are left out: their tests are POSIX- or macOS-only and skip here (CI's and WSL's receipts cover them). Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4c/suite-windows.log",
        "sha256": "37568d9115c892c43fd1955e9f69aae15e4e69688416bb6986ea6f1ac0a9feae"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "4dff7ed3bf828475aa6ed6089ab6168bc42fe5630ee6b4257705a008a34e2cf7",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-MAN-AC10",
      "acceptance": [
        "AC-10"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "Read winpipe's module and function docstrings again against the code at 3586a0d (review-ac10.md): they say the DACL keeps other users out and describe client_is_me as a check a server can make on each connection, which app.py's accept path now makes (M7); nothing claims a check that isn't made.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/review-ac10.md",
        "sha256": "04d466142e24ba4a4ea322c3eea445669268df922d085868d049b392b78bb7a4"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "b6a69cbf91bf19c0cb5b66011cece696b213586d292b8ae81ada2dacc13fe1f5",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "red",
      "status": "deferred",
      "command": [],
      "method": "The drill for macOS's root code: in chatmon/updates.py's _MACOS_ROOT, replace '! -user root -o -perm +022' with '-name nothing', then tests/test_install_update.py::test_mac_an_app_others_could_change_is_never_run_as_root must fail, and pass again once the text is restored.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "d41adef9aa795bff7734a759d8826f0e018ae9827d0ae64d89dea6a5f25a6fda",
      "red": null,
      "reason": "Not run: the test needs macOS (ditto, BSD find, osascript). No Mac is here or in the test lab, and a CI run of a drill branch needs a push, which this worker may not make. Next action: Randy on a Mac, or the coordinator pushing a throwaway branch with the mutation and dispatching ci.yml on it; until then T-03-macos-root stays implemented."
    },
    {
      "id": "W4C-BEH-CI-LINUX",
      "acceptance": [
        "AC-01-LINUX",
        "AC-02",
        "AC-07",
        "AC-09-ORDER",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43729628408",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132858987756",
        "--log"
      ],
      "method": "CI run 43729628408 on 3586a0d, job test (ubuntu-24.04, 3.15): every Linux test of these criteria passed. That is tests/test_install_update.py's root-side tests (a signed newer package installed from root's own copy; a tampered list, a bad signature, an older release and a changed package refused; a caller's checksum never taken; the check loaded only from root's own files), tests/test_packaging.py's postinstall tests (a folder not root's alone gets nothing), tests/test_agents.py's private backups, and tests/test_attachments.py's Linux mount and pipe tests. The same tests passed on ubuntu 3.11, ubuntu-24.04-arm 3.14 and the three distro containers. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto 3586a0d's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-3586a0d.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132858987756-test-ubuntu-24.04-3.15.log",
        "sha256": "da18de8398488879b4578db6fc7c0de2d8018e58498bfeb61f445a0d3e8abc69"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "1714a29cd8d2fc9e944ce56bc6a86383af9abd1b72dd2dfc3ce7ef4c0302fe4c",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-BEH-CI-MACOS",
      "acceptance": [
        "AC-01-MACOS",
        "AC-02",
        "AC-09-REMOTE"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43729628408",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132858987797",
        "--log"
      ],
      "method": "CI run 43729628408 on 3586a0d, job test (macos-latest, 3.14): tests/test_install_update.py's macOS tests passed. They cover a signed newer package installed from a checked copy of Chatmon.app; a bad list, signature or older release refused; an app others could change never run as root; and the AppleScript handing paths over as data. Also passed: tests/test_packaging.py's postinstall tests under BSD ls and tests/test_attachments.py::test_mac_mounts_not_stored_here_are_refused (macOS statfs). The same tests passed on the 3.11 and 3.15 legs. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto 3586a0d's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-3586a0d.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/ci-132858987797-test-macos-latest-3.14.log",
        "sha256": "855fda01d72e8e1a1b33d7a8ef9ad84e82ccf64fb8d3db2249f9961123078526"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "55333bb00eeae285d72f570b7a55bbc709036ba21fb3d9e80dc5ec30fd8da0b9",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-BEH-PKG-CONTAINERS",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43729628343",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132858987200",
        "--log"
      ],
      "method": "Packages run 43729628343, the pull_request run on PR #18 at 3586a0d, whose test merge has 3586a0d's own tree (reports/wave4c/ci/merge-tree.txt: the merge's tree equals 3586a0d's). Job linux. It built the deb and rpm, then installed each on a fresh system, ran it and removed it. In ubuntu:24.04, debian:trixie and fedora:44 containers it ran packaging/linux/test-install-update.sh, root's own update path with no caller's checksum. Each printed 'test-install-update: all good' (log lines 240, 269 and 822), and the job succeeded. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkg-132858987200-linux.log",
        "sha256": "ca291363e2012ef2b851d0d414217ad7e842ee037feade7559aaa9d52d5082f6"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "0d76a1b0a1b330ca0dda9b99664c076d5ac01bf713844c358bdd6fc839547d95",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-BEH-PKG-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43729628343",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132858987473",
        "--log"
      ],
      "method": "Packages run 43729628343, the pull_request run on PR #18 at 3586a0d, whose test merge has 3586a0d's own tree (reports/wave4c/ci/merge-tree.txt: the merge's tree equals 3586a0d's). Job macos (macos-latest). Chatmon.app was installed from the built .pkg. The job checked that it was owned by uid 0 and had Contents/Resources/install-update. Its own frozen verify-update refused files that aren't there with exit 3 (log line 491: 'The update wasn't installed: couldn't read missing.txt'). The macos-15-intel job did the same (pkg-132858987612-macos-macos-15-intel.log, line 587). Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/ci/pkg-132858987473-macos-macos-latest.log",
        "sha256": "c5275efa4ac046778716622d28def1fc8583e747f4d9861ea51130a8f296af2b"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "d41adef9aa795bff7734a759d8826f0e018ae9827d0ae64d89dea6a5f25a6fda",
      "red": null,
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-LINUX-installs-the-copy",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_signed_newer_package_is_installed_from_roots_own_copy"
      ],
      "method": "Red drill AC-01-LINUX-installs-the-copy in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "0d76a1b0a1b330ca0dda9b99664c076d5ac01bf713844c358bdd6fc839547d95",
      "red": {
        "mutation": "AC-01-LINUX-installs-the-copy: in packaging/linux/install-update, '    apt-get install -y \"$dir/update.deb\"' became '    apt-get install -y \"$file\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_signed_newer_package_is_installed_from_roots_own_copy",
        "observed_diagnostic": "_________ test_a_signed_newer_package_is_installed_from_roots_own_copy _________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "865132b13b559696bafc15ae2378d35d48a64053c5b3c634496e306dfd73390a"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-LINUX-launcher-owner",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_the_check_isnt_loaded_from_anything_but_roots_own"
      ],
      "method": "Red drill AC-01-LINUX-launcher-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "0d76a1b0a1b330ca0dda9b99664c076d5ac01bf713844c358bdd6fc839547d95",
      "red": {
        "mutation": "AC-01-LINUX-launcher-owner: in packaging/linux/verify-update, '    return info.st_uid == OWNER and not stat.S_ISLNK(info.st_mode) and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)' became '    return True'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_check_isnt_loaded_from_anything_but_roots_own",
        "observed_diagnostic": "_ test_the_check_isnt_loaded_from_anything_but_roots_own[group-writable module] _",
        "before": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "c4827c01ab14404cc4239f815b0bda683ed1d820a493f7effceb84ce26b40117"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/verify-update",
            "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-LINUX-refusal-stops",
      "acceptance": [
        "AC-01-LINUX"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_a_tampered_list_is_refused_by_root",
        "tests/test_install_update.py::test_an_older_release_is_refused_by_root"
      ],
      "method": "Red drill AC-01-LINUX-refusal-stops in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/linux/install-update",
          "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
        },
        {
          "path": "packaging/linux/nfpm.yaml",
          "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
        },
        {
          "path": "packaging/linux/test-install-update.sh",
          "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
        },
        {
          "path": "packaging/linux/verify-update",
          "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "0d76a1b0a1b330ca0dda9b99664c076d5ac01bf713844c358bdd6fc839547d95",
      "red": {
        "mutation": "AC-01-LINUX-refusal-stops: in packaging/linux/install-update, '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || exit 3' became '\"$dir/SHA256SUMS.txt.sig\" >/dev/null || true'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_tampered_list_is_refused_by_root",
        "observed_diagnostic": "___________________ test_a_tampered_list_is_refused_by_root ____________________",
        "before": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ],
        "mutated": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "72d07c5aaef28531b053ec8e5396b9a5f0449f5c58b6754f0d2e4d9989187e56"
          }
        ],
        "after": [
          {
            "path": "packaging/linux/install-update",
            "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-USER-handoff",
      "acceptance": [
        "AC-01-USER"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_root_is_handed_the_signed_list_never_a_checksum"
      ],
      "method": "Red drill AC-01-USER-handoff through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "d41adef9aa795bff7734a759d8826f0e018ae9827d0ae64d89dea6a5f25a6fda",
      "red": {
        "mutation": "AC-01-USER-handoff: in chatmon/updates.py, '        return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}' became '        return PKEXEC, [HELPER, str(path), sha256(path) if path.exists() else \"0\" * 64], {}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_root_is_handed_the_signed_list_never_a_checksum",
        "observed_diagnostic": "____________ test_root_is_handed_the_signed_list_never_a_checksum _____________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "3f8fb0a17c5dcf0e8ae671cc836c6746331846bd125f81ef21c02ac22bfdd01f"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-VERIFY-signature",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_a_tampered_list_is_refused",
        "tests/test_releasecheck.py::test_a_bad_signature_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-signature through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "535408f846d09b3c1766d946b31485ac4a3a206476ba9b495a266480b92ff86d",
      "red": {
        "mutation": "AC-01-VERIFY-signature: in chatmon/releasecheck.py, '    if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE Refused",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "650a004edd0e380adcab672c8017fe24c91779cd2a58991fe69aacbaf673fac0"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-01-VERIFY-version",
      "acceptance": [
        "AC-01-VERIFY"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_releasecheck.py::test_an_older_or_the_same_version_is_refused"
      ],
      "method": "Red drill AC-01-VERIFY-version through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "535408f846d09b3c1766d946b31485ac4a3a206476ba9b495a266480b92ff86d",
      "red": {
        "mutation": "AC-01-VERIFY-version: in chatmon/releasecheck.py, '    if version_key(version) <= version_key(installed):' became '    if version_key(version) < version_key(installed):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_older_or_the_same_version_is_refused[9.0.0]",
        "observed_diagnostic": "_____________ test_an_older_or_the_same_version_is_refused[9.0.0] _____________",
        "before": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "b9b6887ef9672fce713a3d1335ee6924109e52cced7c1f59bc8c080f3a8cb8d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/releasecheck.py",
            "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-02-owner",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-owner in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "bcb31321703ee81a49c50b364b3714419b0124e28704d0c672e5cb43154ee716",
      "red": {
        "mutation": "AC-02-owner: in packaging/macos/scripts/postinstall, '    [ \"$3\" = \"$OWNER\" ]' became '    [ -n \"$3\" ]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[someone else's]",
        "observed_diagnostic": "__________ test_a_folder_not_roots_alone_gets_nothing[someone else's] __________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "aa6892a51c9f78e6fd1bd32e290cb79df45914b8ae610f6223f599fbe5ef1d10"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-02-writable",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_a_folder_not_roots_alone_gets_nothing"
      ],
      "method": "Red drill AC-02-writable in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. The artifact is the harness's results record, whose observed line names the failing test; the red run's output tail in drills-linux.log begins after that line. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux-results.json",
        "sha256": "53609c1dab3ec1203a4064db3f278be00627393bb2fa64606fda10a331033fb4"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/macos/scripts/postinstall",
          "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "bcb31321703ee81a49c50b364b3714419b0124e28704d0c672e5cb43154ee716",
      "red": {
        "mutation": "AC-02-writable: in packaging/macos/scripts/postinstall, '        d????-??-*) ;;' became '        d*) ;;'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_not_roots_alone_gets_nothing[others can write]",
        "observed_diagnostic": "_________ test_a_folder_not_roots_alone_gets_nothing[others can write] _________",
        "before": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ],
        "mutated": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "9003afd8f52c522942229a199613ede78c3ee983153adb6c427aad68b9d8eaec"
          }
        ],
        "after": [
          {
            "path": "packaging/macos/scripts/postinstall",
            "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-03-owner",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_pipe_someone_else_serves_is_told_nothing"
      ],
      "method": "Red drill AC-03-owner through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "b6a69cbf91bf19c0cb5b66011cece696b213586d292b8ae81ada2dacc13fe1f5",
      "red": {
        "mutation": "AC-03-owner: in chatmon/winpipe.py, '        if not server_is_me(handle):' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_someone_else_serves_is_told_nothing",
        "observed_diagnostic": "_______________ test_a_pipe_someone_else_serves_is_told_nothing _______________",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "3336526d1f73d58c3f011dcaa5b69622d5ee9859d1462b7c7b23f5d8003f160d"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-03-sqos",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winpipe.py::test_a_server_learns_who_you_are_but_can_never_act_as_you"
      ],
      "method": "Red drill AC-03-sqos through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/events.py",
          "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_winpipe.py",
          "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
        }
      ],
      "scope_sha256": "b6a69cbf91bf19c0cb5b66011cece696b213586d292b8ae81ada2dacc13fe1f5",
      "red": {
        "mutation": "AC-03-sqos: in chatmon/winpipe.py, '                             FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, None)' became '                             FILE_FLAG_OVERLAPPED, None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [2] == [1]",
        "observed_diagnostic": "E       assert [2] == [1]",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "66699332eb539426b08f0e08331fa30b1e627abc19b55d8320acdb69f9e6b168"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-04-gate",
      "acceptance": [
        "AC-04"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_elevated_no_agents_command_line_ever_starts"
      ],
      "method": "Red drill AC-04-gate through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/windows/chatmon.iss",
          "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "99e5b466a9c50678b7ea56fcb17485653743ec417b988a76df9711a87eb4842d",
      "red": {
        "mutation": "AC-04-gate: in chatmon/agents.py, '    root\\'s rights (see elevated).\"\"\"\\n    if elevated():' became '    root\\'s rights (see elevated).\"\"\"\\n    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AgentError",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f01e4ff54243befe60f2594294576ecf9f20b52b161f9d15f47d91a14dc11a7f"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-05-revocation-asked",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wintrust.py::test_revocation_is_asked_for_the_whole_chain"
      ],
      "method": "Red drill AC-05-revocation-asked through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "f5055a4bc0a2f06fc59f832cfa3a9c0dbacdc8f15f3131f8f1ab6f50ad1cf17a",
      "red": {
        "mutation": "AC-05-revocation-asked: in chatmon/wintrust.py, '    data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN' became '    data.fdwRevocationChecks = WTD_REVOKE_NONE'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_revocation_is_asked_for_the_whole_chain",
        "observed_diagnostic": "________________ test_revocation_is_asked_for_the_whole_chain _________________",
        "before": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "f4041715f6a13b70ee63a8eeec48135477c5f0dbf4423577e763fd75d1d547a6"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintrust.py",
            "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-05-try-later",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet"
      ],
      "method": "Red drill AC-05-try-later through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "f5055a4bc0a2f06fc59f832cfa3a9c0dbacdc8f15f3131f8f1ab6f50ad1cf17a",
      "red": {
        "mutation": "AC-05-try-later: in chatmon/updates.py, '        if status == \"RevocationUnknown\":' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet",
        "observed_diagnostic": "__ test_a_revoked_certificate_is_never_installed_and_an_unknown_one_not_yet ___",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "e19238a7670e2352a0be1d6e9cd215cc980929e81b05de5ead0b588fe3b7f953"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-06-hold",
      "acceptance": [
        "AC-06"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_the_windows_installer_runs_from_a_copy_nobody_can_change"
      ],
      "method": "Red drill AC-06-hold through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        },
        {
          "path": "tests/test_wintrust.py",
          "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
        }
      ],
      "scope_sha256": "c834199e679cb4bc2f42d904b57eaac6149711d8b3f4d6c29563018d408697e9",
      "red": {
        "mutation": "AC-06-hold: in chatmon/updates.py, '            hold = wintrust.hold(copy)' became '            hold = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_windows_installer_runs_from_a_copy_nobody_can_change",
        "observed_diagnostic": "________ test_the_windows_installer_runs_from_a_copy_nobody_can_change ________",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "0e0dbcacd08ab833223f46c0b3a5dfc535338b509ac023017fc81618ce2ccb67"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-07-private",
      "acceptance": [
        "AC-07"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_backups_are_private_new_files_and_only_the_newest_five_are_kept"
      ],
      "method": "Red drill AC-07-private in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "0fa4cd79ecf8d318154961c9a6e373b98b01eff058d01ce6565be7df7adffb33",
      "red": {
        "mutation": "AC-07-private: in chatmon/agents.py, '            fd = os.open(copy, flags, 0o600)' became '            fd = os.open(copy, flags, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_backups_are_private_new_files_and_only_the_newest_five_are_kept",
        "observed_diagnostic": "_____ test_backups_are_private_new_files_and_only_the_newest_five_are_kept _____",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "b830663bbbade9395fd053da64f3dbf26c535b6bbc4dec39517be3a0307b864b"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-08-codex-top",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_agents.py::test_codex_takes_a_config_with_arrays_inside_arrays",
        "tests/test_agents.py::test_codex_connect_then_disconnect_changes_nothing_but_notify"
      ],
      "method": "Red drill AC-08-codex-top through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/agents.py",
          "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        }
      ],
      "scope_sha256": "0b8fe71286b5fa70b14759bd204c2df2059c5d6b023e08c9983296fab380acc3",
      "red": {
        "mutation": "AC-08-codex-top: in chatmon/agents.py, 'if item.strip() and not item.lstrip().startswith(\"#\")), len(lines))' became 'if item.lstrip().startswith(\"[\")), len(lines))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Couldn't add the notify line cleanly",
        "observed_diagnostic": ">           raise AgentError(_(\"Couldn't add the notify line cleanly; not touching the file.\"))",
        "before": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/agents.py",
            "sha256": "f0520784b203124c03789fc3672b2fec0d41e17dc77ede5c377fa66f2b9d9565"
          }
        ],
        "after": [
          {
            "path": "chatmon/agents.py",
            "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-09-ORDER-look-first",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_folder_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-look-first through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "26416bd16ddd1a0f73ecbd6e55efbe8fa8817c5eda45c1c07516d55cb6d3dc1e",
      "red": {
        "mutation": "AC-09-ORDER-look-first: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_folder_is_refused_without_being_opened",
        "observed_diagnostic": "________________ test_a_folder_is_refused_without_being_opened ________________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-09-ORDER-pipe",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_pipe_or_a_device_is_refused_without_being_opened"
      ],
      "method": "Red drill AC-09-ORDER-pipe in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "26416bd16ddd1a0f73ecbd6e55efbe8fa8817c5eda45c1c07516d55cb6d3dc1e",
      "red": {
        "mutation": "AC-09-ORDER-pipe: in chatmon/attachments.py, '    if not stat.S_ISREG(looked.st_mode):' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pipe_or_a_device_is_refused_without_being_opened",
        "observed_diagnostic": "___________ test_a_pipe_or_a_device_is_refused_without_being_opened ____________",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "b3a2b6d60a6cb721ad98f1359ac27a0eda0b483fd31dc37be3372dc982554860"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-09-ORDER-swap",
      "acceptance": [
        "AC-09-ORDER"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_a_file_swapped_between_the_look_and_the_open_is_refused"
      ],
      "method": "Red drill AC-09-ORDER-swap through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "26416bd16ddd1a0f73ecbd6e55efbe8fa8817c5eda45c1c07516d55cb6d3dc1e",
      "red": {
        "mutation": "AC-09-ORDER-swap: in chatmon/attachments.py, '    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (looked.st_dev, looked.st_ino):' became '    if not stat.S_ISREG(info.st_mode):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6f12e54660c08088c43c10940c35e681a28ac31294e95ef294161c671f0bcd6c"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-09-REMOTE-drive",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_windows_mapped_drives_are_refused_and_local_ones_taken"
      ],
      "method": "Red drill AC-09-REMOTE-drive through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "26416bd16ddd1a0f73ecbd6e55efbe8fa8817c5eda45c1c07516d55cb6d3dc1e",
      "red": {
        "mutation": "AC-09-REMOTE-drive: in chatmon/attachments.py, '_drive_type(drive + \"\\\\\\\\\") == DRIVE_REMOTE:' became '_drive_type(drive + \"\\\\\\\\\") == -1:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E       Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "cbd6221fbdc789cac84f5ffd15eb3f1134e06bc0ce2accb38e53318a0636faf8"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-09-REMOTE-linux",
      "acceptance": [
        "AC-09-REMOTE"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_attachments.py::test_linux_network_and_fuse_mounts_are_refused_but_not_fuseblk"
      ],
      "method": "Red drill AC-09-REMOTE-linux in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills-linux.log",
        "sha256": "c315a2e5de696bad0176b7fa86139cad8bef208c2f20d6edbf72753611c1aa59"
      },
      "inputs": [
        {
          "path": "chatmon/attachments.py",
          "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_attachments.py",
          "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
        }
      ],
      "scope_sha256": "26416bd16ddd1a0f73ecbd6e55efbe8fa8817c5eda45c1c07516d55cb6d3dc1e",
      "red": {
        "mutation": "AC-09-REMOTE-linux: in chatmon/attachments.py, '            kind = LINUX_REMOTE.get(_statfs_type(path) or 0)' became '            kind = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "E           Failed: DID NOT RAISE AttachError",
        "before": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "f54f8d13d71363b7ff5700601047dc3da665806d32f41d36768eb8ca55cfc4ee"
          }
        ],
        "after": [
          {
            "path": "chatmon/attachments.py",
            "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-11-local",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_on_windows_everything_lives_on_this_computer"
      ],
      "method": "Red drill AC-11-local through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "b5fe3b7982facb96398e176fe58d2ddabed64316ee244ad7ba0b6b5e1d17caf4",
      "red": {
        "mutation": "AC-11-local: in chatmon/paths.py, '    if sys.platform == \"win32\":\\n        return _local()' became '    if sys.platform == \"win32\":\\n        return _roaming()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_everything_lives_on_this_computer",
        "observed_diagnostic": "______________ test_on_windows_everything_lives_on_this_computer ______________",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "df7ca4abfa4b50f5a879ce535095332b45941528be6d7009f17e1e656037a544"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-11-newer-wins",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_paths.py::test_they_join_whats_on_this_computer_already_the_newer_file_winning"
      ],
      "method": "Red drill AC-11-newer-wins through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/paths.py",
          "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
        },
        {
          "path": "tests/test_paths.py",
          "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
        },
        {
          "path": "tests/test_rename.py",
          "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
        }
      ],
      "scope_sha256": "b5fe3b7982facb96398e176fe58d2ddabed64316ee244ad7ba0b6b5e1d17caf4",
      "red": {
        "mutation": "AC-11-newer-wins: in chatmon/paths.py, '            if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:' became '            if target.exists():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_they_join_whats_on_this_computer_already_the_newer_file_winning",
        "observed_diagnostic": "____ test_they_join_whats_on_this_computer_already_the_newer_file_winning _____",
        "before": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/paths.py",
            "sha256": "dff1698ecf0d9224354e91cab1608669cc096f88ab521fda98c5565e21a61f74"
          }
        ],
        "after": [
          {
            "path": "chatmon/paths.py",
            "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-12-kind",
      "acceptance": [
        "AC-12"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_chatmon_installed_by_the_system_says_which_package_manager"
      ],
      "method": "Red drill AC-12-kind through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "7a3e912d20ff564895a58bde9172046edef64017e3a7afef0965c9d559a039e6",
      "red": {
        "mutation": "AC-12-kind: in chatmon/updates.py, '                    if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:' became '                    if subprocess.run(query, capture_output=True, timeout=10).returncode != 0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chatmon_installed_by_the_system_says_which_package_manager",
        "observed_diagnostic": "______ test_a_chatmon_installed_by_the_system_says_which_package_manager ______",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "91c8bbd8b7b7c6ec1470e8fcc0ecba1bfa6559fa10dc8806a103ac9b32f2de63"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4C-RED-AC-M6A-14-pin",
      "acceptance": [
        "AC-M6A-14"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill AC-M6A-14-pin through tests/drills/run.py on this Windows workstation, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for 3586a0d, wave4/crash merged.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/wave4c/drills.log",
        "sha256": "a9b84d06242f37e74b8dcb480e7d740af9fae466c37c6ab16ab918ff4ed6273d"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
        }
      ],
      "scope_sha256": "b767465ce49449895e64e866aba189dc5eb2217f03f98e6631e572dd74ed3b46",
      "red": {
        "mutation": "AC-M6A-14-pin: in packaging/build.py, 'chatmon@v{v}' became 'chatmon'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_release_notes_pin_the_pipx_install_to_the_release",
        "observed_diagnostic": "___________ test_release_notes_pin_the_pipx_install_to_the_release ____________",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "7373e5c1acdedf29e61c52bf3f180b0c0ef0144bf16a08ee8f81d3f2081d7e67"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "MAC-RED-AC-01-MACOS",
      "acceptance": [
        "AC-01-MACOS"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/Users/user/chatmon-drills-tmp/venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_install_update.py::test_mac_an_app_others_could_change_is_never_run_as_root"
      ],
      "method": "Red drill MAC-AC-01-MACOS-writable on the owner's MacBook Pro (macOS 15.7.9 24G830, Intel x86_64), owner-approved 2026-11-15, launched from here over ssh with docs/delivery/reports/m1a/mac/job.sh's drills step: tests/drills/run.py, with Homebrew's Python 3.13.7, PyQt6 6.11.0 and pytest 9.2.0 in a venv of its own (packaging/requirements-test.txt, hash-locked; reports/m1a/mac/context-observed.txt), in a temporary copy of a4fe9f8's files (git archive; the unpacked tree checked against the commit's, 6fa4a57f). a4fe9f8 is wave4/mac-drills with improve/assessment-fixes merged (cbeed17, the toast merge, and 86e84e0, the quit guard), which changed none of this criterion's files since 3586a0d. Green; then in _MACOS_ROOT '-o -perm +022' became '-o -name nothing', so find no longer reports a file that group or others can write, and test_mac_an_app_others_could_change_is_never_run_as_root failed in its own body (tests/test_install_update.py:287): the root script exited 0, having run the copied app's install-update and installed, where 3 and the refusal were asserted; the file's bytes were put back (SHA-256 checked) and it passed again. The plan's own text for this drill (W4C-RED-AC-01-MACOS: '! -user root -o -perm +022' becoming '-name nothing') was run too, as MAC-AC-01-MACOS-plan-text in the same log: it also takes out the '! -user root' that the test's fixture puts the test user's uid into, so the test errors at setup on that guard (\"'! -user root' isn't in the script any more\") before the script runs. That proves the guard, not the check, so this receipt binds the drill that keeps that text. The '! -user root' half itself can't be drilled by this test: every file in the test's copy is the test user's own, and only root can make one someone else's. The same drills went green, red and green on 3586a0d earlier the same day (reports/m1a/mac/3586a0d/). The command is the one run there; the receipt's environment is the plan's profile (ROADMAP: evidence from elsewhere).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1a/mac/drills.log",
        "sha256": "b57d8fefffdc4f637903eae9dfd9ea46ff063b19b101df8d667b24150b5a2f55"
      },
      "inputs": [
        {
          "path": "chatmon/releasecheck.py",
          "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "packaging/build.py",
          "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
        },
        {
          "path": "packaging/macos/install-update",
          "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
        }
      ],
      "scope_sha256": "d41adef9aa795bff7734a759d8826f0e018ae9827d0ae64d89dea6a5f25a6fda",
      "red": {
        "mutation": "MAC-AC-01-MACOS-writable: in chatmon/updates.py, '-o -perm +022' became '-o -name nothing'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "returncode=0, stdout='', stderr=''",
        "observed_diagnostic": "E         app=\\'/U...st-of-user/pytest-1/test_mac_an_app_others_could_c0/downloads/SHA256SUMS.txt.sig'], returncode=0, stdout='', stderr='')",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "12088f2c04cd9bcbd1f6c76c1cb560052434de485f5ecab595c92e29587d018b"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "11ac51dc1fdf187e842ab294105317fc37e732493f6b898052fdc41a9fae9c6d",
    "inputs": [
      {
        "path": "chatmon/agents.py",
        "sha256": "684aeff939bebed6f74f00853d98c1285eec7fc5535ed755167549fe3be891b3"
      },
      {
        "path": "chatmon/attachments.py",
        "sha256": "6fd8c7f1c89aedb234e8049a3ef878d897633753a2e97ca7db8ac6e8b3a4f0bb"
      },
      {
        "path": "chatmon/events.py",
        "sha256": "60453d86fabeac6c80325f8493c7cee49b4848636ed11b9b311e8e84761bba44"
      },
      {
        "path": "chatmon/paths.py",
        "sha256": "64e11fdbc8fbd657a8c5e1a87ff79527d92bdd9adac7fa5d8412c80a7f1a9d42"
      },
      {
        "path": "chatmon/releasecheck.py",
        "sha256": "245c8badc1fcf2d32cc7ead09b40a3e71d1adf0ac0de17c67b9f1aff97163655"
      },
      {
        "path": "chatmon/updates.py",
        "sha256": "a619e20d407d185b1b93dacf0f3bc89758a9a5ae8f89ebc5773099427771ea57"
      },
      {
        "path": "chatmon/winpipe.py",
        "sha256": "15d528e2fd2838b153d1dbbbe98b6fdb40c532ca0499f6df8753258766efc634"
      },
      {
        "path": "chatmon/wintrust.py",
        "sha256": "80fc5fc28e8f9b43a5669447fbf85df0173c378e344d35d95d418c4f49ef30ac"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "707da3b7b9fa99f4c09083bc0acbd866abcb7c06b61d4007ba5cdc1cbe2a39a7"
      },
      {
        "path": "docs/delivery/reports/wave4/cilog.py",
        "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
      },
      {
        "path": "docs/delivery/reports/wave4/wsl_drills.py",
        "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
      },
      {
        "path": "packaging/build.py",
        "sha256": "c27e872fde954f9e9d57e142157d5400371049f09334f57e067b1c41588d01ef"
      },
      {
        "path": "packaging/chatmon.spec",
        "sha256": "0e5a8d05d49a2be6ca16fe333f2f6e0f2a0dc11db70d1a22b84ebfafb3d61afb"
      },
      {
        "path": "packaging/linux/install-update",
        "sha256": "e12260b41f46456b9872461785647aa413474605dc1e02ae65cc389e99e1d2fe"
      },
      {
        "path": "packaging/linux/nfpm.yaml",
        "sha256": "1e540dce29d30f4d4ed546c49b5a0336f3d98765c85f5d65d2d35bf2300beb07"
      },
      {
        "path": "packaging/linux/test-install-update.sh",
        "sha256": "4c507928cff3ca6747fa6caa2b7de37852fc999932823bb71382e45ee20b4a06"
      },
      {
        "path": "packaging/linux/verify-update",
        "sha256": "46d526f4116846523da302f83cd94f1c2a2f0a3ca410b4893cd501526230b5bd"
      },
      {
        "path": "packaging/macos/entry.py",
        "sha256": "5743546e35d47f853f0f3741aa871d6defe03f4a1dffa90888b578d30ef12157"
      },
      {
        "path": "packaging/macos/install-update",
        "sha256": "2aeb3dbea121e55bb3f50652e813a194571d532cfdfa13ba73ad6b2dee384b9b"
      },
      {
        "path": "packaging/macos/scripts/postinstall",
        "sha256": "07b9f717e770966a800226cd485a80f8c4f7f76a853fc5ad5e6a3ee3975aa278"
      },
      {
        "path": "packaging/windows/chatmon.iss",
        "sha256": "86001c867d285a61be87fa776a1f12a91ada50d4ae412e1c2587cb527ed1db26"
      },
      {
        "path": "pyproject.toml",
        "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
      },
      {
        "path": "tests/ed25519_sign.py",
        "sha256": "ac3bc5a078fb5077e26a5b6531658f6052288895a8a2ac6eb43ff769dc61b077"
      },
      {
        "path": "tests/test_agents.py",
        "sha256": "c21830c9a1481350dc4118103e141b5c3a20a0b583208d529e3567efaf8c34c9"
      },
      {
        "path": "tests/test_attachments.py",
        "sha256": "542ec6b580475afaf7882b3133464446cf2784b3e4ba8b075e44690a80222eeb"
      },
      {
        "path": "tests/test_install_update.py",
        "sha256": "94b7a779db7e80e01272ee231688e3690991f4693df8e6ae47cadc1e94bfc282"
      },
      {
        "path": "tests/test_packaging.py",
        "sha256": "1e61439d4b2b29340d55b520c12601854ece39955a901832fcaf837726b94be1"
      },
      {
        "path": "tests/test_paths.py",
        "sha256": "1b1c01a5cb28181ab28e35a7d70e042e0c1b558cb5b7ef4da6ff4ef434ef05c5"
      },
      {
        "path": "tests/test_releasecheck.py",
        "sha256": "5e6805ca07fb84c3a231fbdb01b0c5fc170625401aa809fa5af5ecc827b5d9b2"
      },
      {
        "path": "tests/test_rename.py",
        "sha256": "2bc6f8e0b193279895a904cd3b1288b37b50badbb880d0c15db2e2998c188260"
      },
      {
        "path": "tests/test_updates.py",
        "sha256": "d770d014be06e727b398a1a95d514b33b31c99e6bc0b1d0e594dcb5d8a3cc136"
      },
      {
        "path": "tests/test_winpipe.py",
        "sha256": "9db3e69245aafd5908e90357b62c384f1f3d14d8c46384cf4811c9844dd2d7b9"
      },
      {
        "path": "tests/test_wintrust.py",
        "sha256": "c2a6d618063847b9fa4995a0ee8ac0390c61428c94b04af845bad831a7cd7e1a"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    },
    "verified_tasks": [
      "T-01-releasecheck",
      "T-02-linux-root",
      "T-03-macos-root",
      "T-04-postinstall",
      "T-05-pipe-client",
      "T-06-elevated",
      "T-07-revocation",
      "T-08-held-installer",
      "T-09-backups",
      "T-10-codex",
      "T-11-attachments",
      "T-12-local-state",
      "T-13-updater-tests",
      "T-14-notes-pin"
    ],
    "pending_operations": [],
    "next_action": "None for M1A: every task is verified at a4fe9f8 (3586a0d's M1A files, with the toast merge and the quit guard). The narrative above still says AC-01-MACOS's red drill needs a Mac; it ran on the owner's MacBook Pro on 2026-11-15 (MAC-RED-AC-01-MACOS, docs/delivery/reports/m1a/mac/README.md). The narrative is left as it is because the scope fingerprint hashes it: editing it would make every receipt here stale, so the next round that re-binds this plan should note the drill there. A merge that changes a file these receipts bind, or ROADMAP.md, needs those checks run again.",
    "source_revision": "a4fe9f8d2f45b35ba23da6b2b06a689604fca1db"
  }
}
```
