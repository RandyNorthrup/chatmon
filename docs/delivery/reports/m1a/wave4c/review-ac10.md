# AC-10 review, round three: winpipe's docstrings at 3586a0d (2026-11-15)

Round two ([../wave4b/review-ac10.md](../wave4b/review-ac10.md), at bf9d8ac) passed. Its receipt went stale because
ROADMAP.md (a rule) is amended for round three, and wave4/crash changed `chatmon/app.py`, which holds the accept
path. This review reads the docstrings again against the code at `3586a0d`.

- `chatmon/winpipe.py` is unchanged since fb19cb9 (`git diff fb19cb9 3586a0d -- chatmon/winpipe.py` is empty).
  - The module docstring (lines 1-13) still matches `deliver`: `CreateFileW` with
    `SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION` at line 216, then `server_is_me(handle)` at line 228, before any
    write.
  - It also still matches `claim`: the DACL `O:<you>D:(A;;FA;;;<you>)` at line 179.
  - `client_is_me`'s docstring (line 280) still describes the extra check a server may make on each connection, and
    that is what its body does.
- In `app.py`, the crash fix moved the accept path down again but didn't change it. Line 2241 calls
  `_client_is_me(sock)` on Windows for each new connection, and aborts the socket if it fails. The helper is at lines
  3200-3204 and asks `winpipe.client_is_me` about the socket's pipe handle. So "a check offered to the accept path" is
  still what the docstring says and what the code does.
- No docstring claims a check that the code doesn't make.

Result: pass. `tests/test_windows.py::test_a_hooks_own_process_is_you` and `test_the_owner_checks_fail_closed` passed in
round three's Windows suite run ([../../wave4c/suite-windows.log](../../wave4c/suite-windows.log)) and on CI run
43729628408's three Windows legs.
