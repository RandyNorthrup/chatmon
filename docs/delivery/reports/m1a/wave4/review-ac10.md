# AC-10 review again: winpipe's docstrings at fb19cb9, 2026-11-14

The first review ([review-ac10.md](../review-ac10.md), against `6c65c95`) passed. Its receipt went stale because the
files it was bound to changed in later merges, so the docstrings were read again against the code at `fb19cb9`.

- **Module docstring** (`chatmon/winpipe.py`, lines 1-13). It says a hook opens the pipe for identification only and
  checks its server on that handle before it tells it anything. `deliver` (line 205) still does exactly that:
  `CreateFileW` with `SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION` (line 216), then `server_is_me(handle)`
  (line 228) before any write. It says only you can open Chatmon's pipe. `claim` (line 163) still makes it with the
  DACL `O:<you>D:(A;;FA;;;<you>)` (line 179), the same as Qt's `UserAccessOption`. It says `client_is_me` looks at a
  connection's process for a server that wants to see it, and that is what the function does.
- **`client_is_me`'s docstring** (line 280). It says the pipe's access list already keeps other users out, and that
  this is an extra check a server can make on each connection, with `QLocalSocket.socketDescriptor()` as the handle.
  That matches its body (`_peer_is_me` with `GetNamedPipeClientProcessId`).
- **The accept path.** M1A offered the call to M7 (Integration notes 3), and M7 took it: `app.py` line 2203 calls
  `_client_is_me(sock)` on Windows for each new connection. That helper is `winpipe.client_is_me` on the socket's
  descriptor (lines 3143-3147), and its comment says the access list keeps others out and this checks again. The
  docstring's "offered to the accept path" is now also what happens.
- No docstring claims a check that the code doesn't make.

Result: pass. The behavior is unchanged and still covered by `tests/test_windows.py::test_a_hooks_own_process_is_you`
and `test_the_owner_checks_fail_closed`. Both passed in this wave's Windows suite run
([suite-windows.log](../../wave4/suite-windows.log)) and on CI's three Windows legs (run 43677128712).

This review covers fb19cb9 only. Two other workers are changing code at the same time, and neither owns `winpipe.py`.
