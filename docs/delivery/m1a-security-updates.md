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
- Red drills: `docs/delivery/reports/m1a/drills.json`, run by `tests/drills/run.py`.
- Platform-only checks that can't run here are recorded as pending operations in the checkpoint.

## Integration notes

Filled in as the APIs land; the final list is in the closing report.

## Changelog notes

Filled in as the behavior lands.

## README notes

Filled in as the behavior lands.

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
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```
