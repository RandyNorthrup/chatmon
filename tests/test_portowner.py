"""Whose program listens on a port (portowner.py), asked of the real system: a socket this test opens is yours, one
the system's own services hold isn't, and a port nobody listens on is nobody's."""

import os
import socket
import sys
from pathlib import Path

import pytest

from chatmon import portowner

supported = pytest.mark.skipif(sys.platform not in ("win32", "darwin") and not sys.platform.startswith("linux"), reason="Linux, Windows and macOS only")


def _listening(family=socket.AF_INET, host="127.0.0.1"):
    s = socket.socket(family)
    s.bind((host, 0))
    s.listen()
    return s


@supported
def test_a_socket_of_yours_is_yours_and_a_closed_port_nobodys():
    with _listening() as s4:
        assert portowner.mine(s4.getsockname()[1]) is True
    with _listening(socket.AF_INET6, "::1") as s6:
        assert portowner.mine(s6.getsockname()[1]) is True
    closed = _listening()
    port = closed.getsockname()[1]
    closed.close()
    assert portowner.mine(port) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' own RPC service")
def test_on_windows_a_port_the_system_holds_isnt_yours():
    # 135: the RPC endpoint mapper, always listening, run by svchost as NETWORK SERVICE.
    pids = portowner._listening_pids(135)
    if not pids:
        pytest.skip("nothing listens on 135 here")
    assert portowner.mine(135) is False and not any(portowner._runs_as_me(pid) for pid in pids)
    assert portowner._runs_as_me(os.getpid())


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux's /proc/net/tcp")
def test_on_linux_a_port_another_account_listens_on_isnt_yours():
    others = []
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in Path(table).read_text().splitlines()[1:]:
            f = line.split()
            if f[3] == portowner.LISTEN and int(f[7]) != os.getuid():
                others.append(int(f[1].rsplit(":", 1)[1], 16))
    if not others:
        pytest.skip("no other account listens on anything here")
    assert portowner.mine(others[0]) is False


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux's /proc/net/tcp")
def test_on_linux_your_socket_and_someone_elses_on_one_port_isnt_yours(monkeypatch, tmp_path):
    """Both counted: a server of yours on 127.0.0.1 doesn't make someone else's on [::1] yours."""
    me = os.getuid()
    line = "  0: {addr}:2CAA 00000000:0000 0A 00000000:00000000 00:00000000 00000000  {uid}        0 1 1 0000000000000000 100 0 0 10 0\n"
    head = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
    (tmp_path / "tcp").write_text(head + line.format(addr="0100007F", uid=me))
    (tmp_path / "tcp6").write_text(head + line.format(addr="00000000000000000000000001000000", uid=me + 1))
    real = Path

    def fake(name, *args):
        return real(tmp_path / Path(name).name) if str(name).startswith("/proc/net/") else real(name, *args)

    monkeypatch.setattr(portowner, "Path", fake)
    assert portowner.mine(0x2CAA) is False
    (tmp_path / "tcp6").write_text(head)
    assert portowner.mine(0x2CAA) is True
