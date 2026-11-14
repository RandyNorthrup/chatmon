# AC-10 review: winpipe's docstrings, 2026-11-14

M1A-10 found that `winpipe.client_is_me` was never called, while the module docstring said "Chatmon checks
that each client runs as you before it listens to it". The assessment allows either calling it on accept or
making the docstring true. `app.py`, where connections are accepted, is M0's, so the docstrings were made
true (commit `db4abd4`) and the call is offered to M7 (Integration notes 3).

Read against the code at `6c65c95`:

- The module docstring now says a hook opens the pipe for identification only and checks its server on that
  handle (`deliver`, which does exactly that: `CreateFileW` with `SECURITY_SQOS_PRESENT |
  SECURITY_IDENTIFICATION`, then `server_is_me(handle)` before any write); that Chatmon's pipe can be opened by
  you alone (`claim` creates it with the DACL `O:<you>D:(A;;FA;;;<you>)`, the same as Qt's `UserAccessOption`,
  which `app.open_server` sets); and that `client_is_me` is there for a server that wants to look at each
  connection. All three match the code.
- `client_is_me`'s own docstring says the access list already keeps other users out and names the handle to
  pass (`QLocalSocket.socketDescriptor()`). Its behavior is unchanged and covered by
  `tests/test_windows.py::test_a_hooks_own_process_is_you` and `test_the_owner_checks_fail_closed`.
- Nothing claims a check that isn't made.

Result: pass.
