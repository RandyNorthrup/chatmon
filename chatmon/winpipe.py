"""Who is at the other end of a named pipe, on Windows.

Pipe names are one namespace for the whole PC: any user can create
`\\\\.\\pipe\\chatmon-<you>` before your Chatmon does. So a hook checks that the
pipe's server runs as you before it tells it anything, and Chatmon checks that
each client runs as you before it listens to it. Anything that can't be
checked counts as someone else's.

Only ctypes and the Windows API; imported on Windows alone."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_USER = 1  # the TOKEN_INFORMATION_CLASS that gives the token's user
ERROR_ACCESS_DENIED = 5
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_PIPE_BUSY = 231
# The pipe as Qt's QLocalServer makes it: both ways, bytes, as many instances as it likes, no remote clients.
PIPE_ACCESS_DUPLEX = 0x3
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x80000
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_REJECT_REMOTE_CLIENTS = 0x8
PIPE_UNLIMITED_INSTANCES = 255
SDDL_REVISION_1 = 1
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)


def _declare(fn, restype, *argtypes):
    fn.restype, fn.argtypes = restype, list(argtypes)
    return fn


_GetNamedPipeServerProcessId = _declare(_kernel32.GetNamedPipeServerProcessId, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG))
_GetNamedPipeClientProcessId = _declare(_kernel32.GetNamedPipeClientProcessId, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG))
_OpenProcess = _declare(_kernel32.OpenProcess, wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_GetCurrentProcess = _declare(_kernel32.GetCurrentProcess, wintypes.HANDLE)
_CloseHandle = _declare(_kernel32.CloseHandle, wintypes.BOOL, wintypes.HANDLE)
_OpenProcessToken = _declare(_advapi32.OpenProcessToken, wintypes.BOOL, wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
_GetTokenInformation = _declare(
    _advapi32.GetTokenInformation, wintypes.BOOL, wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
)
_IsValidSid = _declare(_advapi32.IsValidSid, wintypes.BOOL, ctypes.c_void_p)
_GetLengthSid = _declare(_advapi32.GetLengthSid, wintypes.DWORD, ctypes.c_void_p)
_EqualSid = _declare(_advapi32.EqualSid, wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p)
_ConvertSidToStringSid = _declare(_advapi32.ConvertSidToStringSidW, wintypes.BOOL, ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR))
_ConvertStringSecurityDescriptorToSecurityDescriptor = _declare(
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW,
    wintypes.BOOL, wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.ULONG),
)
_LocalFree = _declare(_kernel32.LocalFree, ctypes.c_void_p, ctypes.c_void_p)


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", wintypes.BOOL)]


_CreateNamedPipe = _declare(
    _kernel32.CreateNamedPipeW,
    wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(_SecurityAttributes),
)


def my_identity() -> str | None:
    """"<your SID>-<session>": who you are and which session this is. Pipe names are shared by every session on
    the PC (only events and the like are kept apart per session), so the pipe's name has both: you at the
    console and over Remote Desktop get a Chatmon each, and two people named alike in two domains never meet.
    https://learn.microsoft.com/en-us/windows/win32/termserv/kernel-object-namespaces"""
    sid = _user_sid(_GetCurrentProcess())
    if sid is None:
        return None
    text = wintypes.LPWSTR()
    if not _ConvertSidToStringSid(sid, ctypes.byref(text)):
        return None
    try:
        me = text.value
    finally:
        _LocalFree(ctypes.cast(text, ctypes.c_void_p))
    session = wintypes.DWORD()
    if not _kernel32.ProcessIdToSessionId(_kernel32.GetCurrentProcessId(), ctypes.byref(session)):
        return None
    return f"{me}-{session.value}"


def full_name(name: str) -> str:
    """A QLocalServer name as Windows knows the pipe."""
    return name if name.startswith("\\\\") else "\\\\.\\pipe\\" + name


def claim(name: str) -> int | None:
    """Make the first instance of the pipe `name`, which only the current user may use, so that the
    name is ours before Qt adds the instances it listens on. (Qt can't ask for the first instance.)
    None if the name is taken already, by anyone; raises OSError if it can't tell."""
    sid = _user_sid(_GetCurrentProcess())
    if sid is None:
        raise OSError("can't read the current user's SID")
    text = wintypes.LPWSTR()
    if not _ConvertSidToStringSid(sid, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        me = text.value
    finally:
        _LocalFree(ctypes.cast(text, ctypes.c_void_p))
    descriptor = ctypes.c_void_p()
    # The same as QLocalServer's UserAccessOption: you own it, and you alone have any access.
    if not _ConvertStringSecurityDescriptorToSecurityDescriptor(f"O:{me}D:(A;;FA;;;{me})", SDDL_REVISION_1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
        handle = _CreateNamedPipe(
            full_name(name),
            PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE | FILE_FLAG_OVERLAPPED,
            PIPE_REJECT_REMOTE_CLIENTS,
            PIPE_UNLIMITED_INSTANCES, 0, 0, 0,
            ctypes.byref(attributes),
        )
        error = ctypes.get_last_error()
    finally:
        _LocalFree(descriptor)
    if handle in (None, INVALID_HANDLE_VALUE):
        if error in (ERROR_ACCESS_DENIED, ERROR_PIPE_BUSY):
            return None
        raise ctypes.WinError(error)
    return handle


def release(handle: int) -> None:
    """Let go of a `claim`; the instances Qt listens on keep the name."""
    _CloseHandle(handle)


def server_is_me(handle: int) -> bool:
    """A client's end of a pipe: does the process serving it run as the current user?"""
    return _peer_is_me(handle, _GetNamedPipeServerProcessId)


def client_is_me(handle: int) -> bool:
    """A server's end of a pipe: does the process connected to it run as the current user?"""
    return _peer_is_me(handle, _GetNamedPipeClientProcessId)


def _peer_is_me(handle: int, peer_pid) -> bool:
    if not handle:
        return False
    pid = wintypes.ULONG()
    if not peer_pid(handle, ctypes.byref(pid)):
        return False
    me = _user_sid(_GetCurrentProcess())
    process = _OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return False  # most likely another user's process, which we may not even look at
    try:
        peer = _user_sid(process)
    finally:
        _CloseHandle(process)
    return me is not None and peer is not None and bool(_EqualSid(me, peer))


def _user_sid(process: int) -> ctypes.Array | None:
    """A copy of the SID of the user a process runs as, or None if it can't be read."""
    token = wintypes.HANDLE()
    if not _OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        size = wintypes.DWORD()
        _GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(size))
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not size.value:
            return None
        info = ctypes.create_string_buffer(size.value)
        if not _GetTokenInformation(token, TOKEN_USER, info, size, ctypes.byref(size)):
            return None
        sid = _SidAndAttributes.from_buffer(info).Sid
        if not sid or not _IsValidSid(sid):
            return None
        return ctypes.create_string_buffer(ctypes.string_at(sid, _GetLengthSid(sid)))
    finally:
        _CloseHandle(token)
