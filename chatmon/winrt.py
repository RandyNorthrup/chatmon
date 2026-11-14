"""Windows Runtime objects through combase, with ctypes: no WinRT package for Python needed. What winfocus.py
(Windows 11's Focus) and wintoast.py (notifications) share: GUIDs, HSTRINGs, activation factories, calling a
method by its vtable slot, and a delegate of Chatmon's own for Windows to call back. Used on Windows alone.

A WinRT object is a COM object: a pointer to a table of methods, IUnknown's 3 first (QueryInterface, AddRef,
Release), then IInspectable's 3, then the interface's own in the order the Windows SDK's headers give them
(winrt/*.h). Each method takes the object first and returns an HRESULT; a negative one is a failure, which ctypes
raises as OSError.
https://learn.microsoft.com/en-us/windows/win32/api/roapi/nf-roapi-rogetactivationfactory
https://learn.microsoft.com/en-us/windows/win32/api/winstring/nf-winstring-windowscreatestring"""

from __future__ import annotations

import ctypes
import threading
import time
import uuid
from ctypes import wintypes
from typing import Callable

IID_IUNKNOWN = "00000000-0000-0000-c000-000000000046"
IID_IAGILE_OBJECT = "94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90"  # callable from any thread, never marshalled
E_NOINTERFACE = -0x7FFFBFFE  # 0x80004002, as the signed HRESULT it is
FREE_AFTER = 10.0  # seconds a delegate everyone let go of is kept, in case its last Release is still returning

# Windows' calling convention and HRESULT, which ctypes has on Windows alone: elsewhere this module imports and
# does nothing.
_FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_HRESULT = getattr(ctypes, "HRESULT", ctypes.c_long)


class GUID(ctypes.Structure):
    _fields_ = [("bytes", ctypes.c_ubyte * 16)]

    @classmethod
    def of(cls, text: str) -> "GUID":
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)

    def __str__(self) -> str:
        return str(uuid.UUID(bytes_le=bytes(self.bytes)))


def method(obj: int, slot: int, *argtypes):
    """The object's method in vtable slot `slot`, ready to call with the object and then `argtypes`."""
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return _FUNCTYPE(_HRESULT, ctypes.c_void_p, *argtypes)(table[slot])


def release(obj: int | None) -> None:
    if obj:
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        _FUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(obj)


def query(obj: int, iid: str) -> int | None:
    """The object's interface `iid` (released by the caller), or None if it hasn't that one."""
    out = ctypes.c_void_p()
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    qi = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(table[0])
    if qi(obj, ctypes.byref(GUID.of(iid)), ctypes.byref(out)) < 0:
        return None
    return out.value or None


def get_object(obj: int, slot: int) -> int | None:
    """A property getter or factory method that hands back one object (released by the caller)."""
    out = ctypes.c_void_p()
    method(obj, slot, ctypes.POINTER(ctypes.c_void_p))(obj, ctypes.byref(out))
    return out.value or None


_combase = None


def combase():
    global _combase
    if _combase is None:
        lib = ctypes.WinDLL("combase")
        lib.WindowsCreateString.argtypes = [wintypes.LPCWSTR, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        lib.WindowsDeleteString.argtypes = [ctypes.c_void_p]
        lib.WindowsGetStringRawBuffer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        lib.WindowsGetStringRawBuffer.restype = ctypes.c_void_p
        lib.RoGetActivationFactory.argtypes = [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        lib.RoActivateInstance.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        _combase = lib
    return _combase


class HString:
    """A Windows string (HSTRING) for the length of a `with`: `.handle` is what methods take."""

    def __init__(self, text: str):
        self.text = text.replace("\0", "")  # an embedded NUL would end the text early
        self.handle = ctypes.c_void_p()

    def __enter__(self) -> "HString":
        units = len(self.text.encode("utf-16-le")) // 2  # its length in UTF-16 code units, not characters
        if units and combase().WindowsCreateString(self.text, units, ctypes.byref(self.handle)) != 0:
            raise OSError("WindowsCreateString failed")
        return self  # the empty string is the null HSTRING

    def __exit__(self, *exc) -> None:
        if self.handle.value:
            combase().WindowsDeleteString(self.handle)
            self.handle = ctypes.c_void_p()


def text_of(handle: int | None) -> str:
    """What an HSTRING says (the caller still owns it)."""
    if not handle:
        return ""
    length = ctypes.c_uint32()
    buffer = combase().WindowsGetStringRawBuffer(handle, ctypes.byref(length))
    return ctypes.wstring_at(buffer, length.value) if buffer else ""


def take_text(handle: ctypes.c_void_p) -> str:
    """What an HSTRING a method handed back says, deleting it."""
    try:
        return text_of(handle.value)
    finally:
        if handle.value:
            combase().WindowsDeleteString(handle)


COINIT_APARTMENTTHREADED = 0x2
RPC_E_CHANGED_MODE = -0x7FFEFEFA  # 0x80010106: the thread already joined COM, the other way


def join_com() -> bool:
    """Have this thread join COM, single-threaded as Qt's windows platform does (OleInitialize), if nothing has
    yet: Qt's offscreen platform doesn't. True if COM can be used on it."""
    try:
        ole32 = ctypes.WinDLL("ole32")
    except (AttributeError, OSError):
        return False
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    joined = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    return joined >= 0 or joined == RPC_E_CHANGED_MODE  # S_FALSE: it already had; never undone, as Qt's isn't


def factory(class_name: str, iid: str) -> int | None:
    """The runtime class's activation factory or statics as interface `iid` (released by the caller), or None
    where this Windows hasn't the class (REGDB_E_CLASSNOTREG) or the interface. On a thread that has joined COM."""
    out = ctypes.c_void_p()
    with HString(class_name) as name:
        found = combase().RoGetActivationFactory(name.handle, ctypes.byref(GUID.of(iid)), ctypes.byref(out))
    return out.value if found == 0 and out.value else None


def activate(class_name: str) -> int | None:
    """A new instance of a runtime class with a default constructor (its IInspectable, released by the caller)."""
    out = ctypes.c_void_p()
    with HString(class_name) as name:
        made = combase().RoActivateInstance(name.handle, ctypes.byref(out))
    return out.value if made == 0 and out.value else None


class EventToken(ctypes.Structure):
    """What add_<Event> hands back, for remove_<Event> to take."""

    _fields_ = [("value", ctypes.c_int64)]


_QUERY = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
_COUNT = _FUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
_INVOKE = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class _Vtable(ctypes.Structure):
    _fields_ = [("QueryInterface", _QUERY), ("AddRef", _COUNT), ("Release", _COUNT), ("Invoke", _INVOKE)]


class _Object(ctypes.Structure):
    _fields_ = [("vtable", ctypes.POINTER(_Vtable))]


class Delegate:
    """A WinRT delegate (a TypedEventHandler, say) made here: Windows calls `invoke(sender, args)` through it,
    on a thread of its own. It says it's agile, so Windows calls it as it is rather than looking for a way to
    marshal it to the thread that made it. Kept alive while Windows holds it; `release()` gives up Chatmon's
    own reference once it's handed over."""

    _held: set["Delegate"] = set()  # alive while anyone holds one
    _done: list[tuple[float, "Delegate"]] = []  # let go of by everyone, freed a while later: never inside a call

    def __init__(self, iid: str, invoke: Callable[[int, int], None]):
        now = time.monotonic()
        Delegate._done[:] = [(when, d) for when, d in Delegate._done if now - when < FREE_AFTER]
        self._iids = {bytes(GUID.of(i).bytes) for i in (iid, IID_IUNKNOWN, IID_IAGILE_OBJECT)}
        self._invoke = invoke
        self._lock = threading.Lock()
        self._count = 1
        self._table = _Vtable(_QUERY(self._query), _COUNT(self._add_ref), _COUNT(self._release), _INVOKE(self._call))
        self._object = _Object(ctypes.pointer(self._table))
        self.pointer = ctypes.addressof(self._object)
        Delegate._held.add(self)

    def _query(self, this, iid, out) -> int:
        if bytes(iid.contents.bytes) in self._iids:
            out[0] = this
            self._add_ref(this)
            return 0
        out[0] = None
        return E_NOINTERFACE

    def _add_ref(self, this) -> int:
        with self._lock:
            self._count += 1
            return self._count

    def _release(self, this) -> int:
        with self._lock:
            self._count -= 1
            count = self._count
        if count == 0:
            Delegate._held.discard(self)
            Delegate._done.append((time.monotonic(), self))
        return count

    def _call(self, this, sender, args) -> int:
        try:
            self._invoke(sender or 0, args or 0)
        except Exception:  # nothing may escape into Windows' thread: the event is just missed
            pass
        return 0

    def release(self) -> None:
        self._release(None)

    @property
    def references(self) -> int:
        return self._count
