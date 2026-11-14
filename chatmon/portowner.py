"""Whose program is listening on a port of this computer.

Automatic hands your questions only to a model server you run yourself (brains.trusted): on a shared computer anyone
can open port 11434 first and read every chat Automatic sent it. Linux says who owns each listening socket in
/proc/net/tcp; Windows says which process does (GetExtendedTcpTable), and that process's token says whose it is;
macOS has lsof, which without root sees only your own processes' sockets.

Only the standard library and the system's own interfaces."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

LISTEN = "0A"  # a socket's state in /proc/net/tcp: listening
LSOF = "/usr/sbin/lsof"
LSOF_TIMEOUT_S = 3


def mine(port: int) -> bool | None:
    """True: something is listening on `port` (on any address) and every listener is a process of yours. False:
    nothing listens there, or something that isn't yours does. None: this computer can't say."""
    try:
        if sys.platform.startswith("linux"):
            return _linux(port)
        if sys.platform == "win32":
            return _windows(port)
        if sys.platform == "darwin":
            return _mac(port)
    except (OSError, ValueError):
        return None
    return None


def _linux(port: int) -> bool | None:
    owners = []
    read = False
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text(encoding="ascii").splitlines()[1:]
        except OSError:
            continue
        read = True
        for line in lines:
            # sl local_address rem_address st tx_queue:rx_queue tr:tm->when retrnsmt uid ...
            fields = line.split()
            if len(fields) > 7 and fields[3] == LISTEN and int(fields[1].rsplit(":", 1)[1], 16) == port:
                owners.append(int(fields[7]))
    if not read:
        return None
    return bool(owners) and all(uid == os.getuid() for uid in owners)


def _mac(port: int) -> bool | None:
    # Without root, lsof lists only sockets of processes you may look into: your own. Another user's listener on
    # the same port goes unseen, so this is as far as macOS lets an ordinary program see.
    if not os.access(LSOF, os.X_OK):
        return None
    try:
        out = subprocess.run([LSOF, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fu"], capture_output=True, text=True, timeout=LSOF_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    uids = [int(line[1:]) for line in out.stdout.splitlines() if line.startswith("u") and line[1:].isdigit()]
    return bool(uids) and all(uid == os.getuid() for uid in uids)


def _windows(port: int) -> bool | None:
    pids = _listening_pids(port)
    if pids is None:
        return None
    return bool(pids) and all(_runs_as_me(pid) for pid in pids)


# -- Windows

AF_INET, AF_INET6 = 2, 23
TCP_TABLE_OWNER_PID_LISTENER = 3
ERROR_INSUFFICIENT_BUFFER = 122
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_USER = 1


def _listening_pids(port: int) -> set[int] | None:
    import ctypes
    from ctypes import wintypes

    class Row4(ctypes.Structure):  # MIB_TCPROW_OWNER_PID
        _fields_ = [("state", wintypes.DWORD), ("local_addr", wintypes.DWORD), ("local_port", wintypes.DWORD),
                    ("remote_addr", wintypes.DWORD), ("remote_port", wintypes.DWORD), ("pid", wintypes.DWORD)]

    class Row6(ctypes.Structure):  # MIB_TCP6ROW_OWNER_PID
        _fields_ = [("local_addr", ctypes.c_ubyte * 16), ("local_scope", wintypes.DWORD), ("local_port", wintypes.DWORD),
                    ("remote_addr", ctypes.c_ubyte * 16), ("remote_scope", wintypes.DWORD), ("remote_port", wintypes.DWORD),
                    ("state", wintypes.DWORD), ("pid", wintypes.DWORD)]

    table = ctypes.WinDLL("iphlpapi").GetExtendedTcpTable
    table.restype = wintypes.DWORD
    table.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
    pids: set[int] = set()
    for family, row in ((AF_INET, Row4), (AF_INET6, Row6)):
        size = wintypes.DWORD(0)
        for _ in range(5):  # the table can grow between asking its size and reading it
            buffer = ctypes.create_string_buffer(max(size.value, 4))
            result = table(buffer, ctypes.byref(size), False, family, TCP_TABLE_OWNER_PID_LISTENER, 0)
            if result != ERROR_INSUFFICIENT_BUFFER:
                break
        if result != 0:
            return None
        count = wintypes.DWORD.from_buffer(buffer).value
        offset = ctypes.sizeof(wintypes.DWORD)  # the rows follow the count; DWORD-aligned, so no padding
        if offset + count * ctypes.sizeof(row) > len(buffer):
            return None
        for entry in (row * count).from_buffer(buffer, offset):
            if ((entry.local_port & 0xFF) << 8 | (entry.local_port >> 8) & 0xFF) == port:  # network byte order
                pids.add(int(entry.pid))
    return pids


def _runs_as_me(pid: int) -> bool:
    """Does process `pid` run as the current user? One that can't be looked into (another user's, the system's)
    counts as someone else's."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    if pid == os.getpid():
        return True
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        return False
    try:
        theirs = _user_sid(process)
    finally:
        kernel32.CloseHandle(process)
    return theirs is not None and theirs == _user_sid(kernel32.GetCurrentProcess())


def _user_sid(process: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(size))
        if not size.value:
            return None
        info = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, TOKEN_USER, info, size, ctypes.byref(size)):
            return None
        sid = ctypes.c_void_p.from_buffer(info).value  # TOKEN_USER starts with SID_AND_ATTRIBUTES, which starts with the SID
        text = wintypes.LPWSTR()
        if not sid or not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            return None
        try:
            return text.value
        finally:
            kernel32.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    finally:
        kernel32.CloseHandle(token)
