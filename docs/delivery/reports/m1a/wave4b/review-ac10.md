# AC-10 review, round two: winpipe's docstrings at bf9d8ac (2026-11-15)

Round one ([../wave4/review-ac10.md](../wave4/review-ac10.md), at fb19cb9) passed. Its receipt went stale because
other files bound to it changed. This review reads the docstrings again against the code at `bf9d8ac`.

- `chatmon/winpipe.py` is unchanged since fb19cb9 (`git diff fb19cb9 bf9d8ac -- chatmon/winpipe.py` is empty).
  - The module docstring (lines 1-13) still matches `deliver`: `CreateFileW` with
    `SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION` at line 216, then `server_is_me(handle)` at line 228 before any
    write.
  - It also still matches `claim`: the DACL `O:<you>D:(A;;FA;;;<you>)` at line 179.
  - `client_is_me`'s docstring (line 280) still describes the extra check a server may make on each connection, and
    that is what its body does.
- The accept path in `app.py` moved down one line. Line 2204 now calls `_client_is_me(sock)` on Windows for each new
  connection, and the helper is at lines 3144-3148. So "a check offered to the accept path" is still what the docstring
  says and what the code does.
- No docstring claims a check that the code doesn't make.

Result: pass. `tests/test_windows.py::test_a_hooks_own_process_is_you` and `test_the_owner_checks_fail_closed` passed in
round two's Windows suite run ([../../wave4b/suite-windows.log](../../wave4b/suite-windows.log)) and on CI run
43701523023's three Windows legs.

Evidence for bf9d8ac only. Another worker (wave4/crash) may change code for an intermittent Qt crash. It doesn't own
`winpipe.py`.
