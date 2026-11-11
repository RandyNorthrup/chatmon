"""Windows: what's dropped on the ask box, or pasted into it, read straight from Windows' own data object
(IDataObject): files, files that aren't on disk (out of Outlook, a zip folder, a browser: winfiles.py), a
picture, or text.

Qt reads a drop's data everywhere else, but not files that aren't on disk: asked for their contents
(FileContents) as memory, Explorer's zip folders answer with a stream, and Qt, which doesn't look at what
kind of answer it got, reads the stream as memory and corrupts the heap (Qt 6.11's qwindowsmimeregistry.cpp,
getData). So the ask box's window has a drop target of Chatmon's own (IDropTarget, registered in place of
Qt's), which takes each answer as what Windows says it is, and a paste of such files reads them from the
clipboard's data object (OleGetClipboard). Imported on Windows alone.
https://learn.microsoft.com/en-us/windows/win32/api/oleidl/nn-oleidl-idroptarget
https://learn.microsoft.com/en-us/windows/win32/api/ole2/nf-ole2-registerdragdrop
https://learn.microsoft.com/en-us/windows/win32/api/objidl/nf-objidl-idataobject-getdata
https://learn.microsoft.com/en-us/windows/win32/shell/clipboard
"""

from __future__ import annotations

import ctypes
import struct
import uuid
from ctypes import POINTER, byref, c_void_p, wintypes
from typing import Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage

from . import winfiles
from .attachments import MAX_FILE

S_OK = 0
E_NOINTERFACE = -0x7FFFBFFE  # 0x80004002
E_UNEXPECTED = -0x7FFF0001  # 0x8000FFFF
DROPEFFECT_NONE, DROPEFFECT_COPY = 0, 1
DVASPECT_CONTENT = 1
TYMED_HGLOBAL, TYMED_ISTREAM = 1, 4
CF_DIB, CF_UNICODETEXT, CF_HDROP, CF_DIBV5 = 8, 13, 15, 17
STREAM_SEEK_SET = 0
CHUNK = 1 << 16
IID_IUNKNOWN = uuid.UUID("00000000-0000-0000-c000-000000000046").bytes_le
IID_IDROPTARGET = uuid.UUID("00000122-0000-0000-c000-000000000046").bytes_le
# IDataObject's methods after IUnknown's three; IStream's.
GET_DATA, QUERY_GET_DATA = 3, 5
STREAM_READ, STREAM_SEEK = 3, 5


class FORMATETC(ctypes.Structure):
    _fields_ = [("cfFormat", wintypes.WORD), ("ptd", c_void_p), ("dwAspect", wintypes.DWORD), ("lindex", wintypes.LONG), ("tymed", wintypes.DWORD)]


class STGMEDIUM(ctypes.Structure):
    _fields_ = [("tymed", wintypes.DWORD), ("handle", c_void_p), ("pUnkForRelease", c_void_p)]  # handle: HGLOBAL or IStream*


_ole32, _user32, _shell32, _kernel32 = (ctypes.WinDLL(name) for name in ("ole32", "user32", "shell32", "kernel32"))
_ole32.ReleaseStgMedium.argtypes = [POINTER(STGMEDIUM)]
_ole32.OleGetClipboard.argtypes = [POINTER(c_void_p)]
_ole32.RegisterDragDrop.argtypes = [wintypes.HWND, c_void_p]
_ole32.RevokeDragDrop.argtypes = [wintypes.HWND]
_kernel32.GlobalLock.restype, _kernel32.GlobalLock.argtypes = c_void_p, [c_void_p]
_kernel32.GlobalUnlock.argtypes = [c_void_p]
_kernel32.GlobalSize.restype, _kernel32.GlobalSize.argtypes = ctypes.c_size_t, [c_void_p]
_user32.RegisterClipboardFormatW.restype, _user32.RegisterClipboardFormatW.argtypes = wintypes.UINT, [wintypes.LPCWSTR]
_shell32.DragQueryFileW.restype, _shell32.DragQueryFileW.argtypes = wintypes.UINT, [c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
CF_DESCRIPTORS = _user32.RegisterClipboardFormatW("FileGroupDescriptorW")
CF_CONTENTS = _user32.RegisterClipboardFormatW("FileContents")
CF_PNG = _user32.RegisterClipboardFormatW("PNG")


def _method(obj: int, slot: int, *argtypes, restype=ctypes.c_long):
    table = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(table[slot])


def _release(obj: int) -> None:
    _method(obj, 2, restype=ctypes.c_ulong)(obj)


def bmp(dib: bytes) -> bytes | None:
    """A device-independent bitmap (CF_DIB, CF_DIBV5) as a .bmp file: its header added, saying where the
    pixels start (after the bitmap's header, its colour masks and its colour table)."""
    if len(dib) < 40:
        return None
    size, _, _, _, bits, compression, _, _, _, used = struct.unpack_from("<IiiHHIIiiI", dib)
    masks = {3: 12, 6: 16}.get(compression, 0) if size == 40 else 0  # BI_BITFIELDS, BI_ALPHABITFIELDS after a short header
    colours = used or (1 << bits if bits <= 8 else 0)
    return b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + size + masks + colours * 4) + dib


class DataObject:
    """An IDataObject, for as long as the call that handed it over (a drop), or held (the clipboard's)."""

    def __init__(self, ptr: int):
        self.ptr = ptr

    def has(self, cf: int) -> bool:
        etc = FORMATETC(cf, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL | TYMED_ISTREAM)
        return _method(self.ptr, QUERY_GET_DATA, POINTER(FORMATETC))(self.ptr, byref(etc)) == S_OK

    def data(self, cf: int, lindex: int = -1, limit: int = MAX_FILE) -> bytes | None:
        """The format's bytes, at most `limit` + 1 of them, as memory or as a stream, whichever Windows says
        it gave; None if it gave neither."""
        etc, medium = FORMATETC(cf, None, DVASPECT_CONTENT, lindex, TYMED_HGLOBAL | TYMED_ISTREAM), STGMEDIUM()
        try:
            if _method(self.ptr, GET_DATA, POINTER(FORMATETC), POINTER(STGMEDIUM))(self.ptr, byref(etc), byref(medium)) != S_OK:
                return None
        except OSError:
            return None
        try:
            if medium.tymed == TYMED_HGLOBAL and medium.handle:
                size = min(_kernel32.GlobalSize(medium.handle), limit + 1)
                at = _kernel32.GlobalLock(medium.handle)
                if not at:
                    return None
                try:
                    return ctypes.string_at(at, size)
                finally:
                    _kernel32.GlobalUnlock(medium.handle)
            if medium.tymed == TYMED_ISTREAM and medium.handle:
                return self._stream(medium.handle, limit)
            return None
        finally:
            _ole32.ReleaseStgMedium(byref(medium))

    @staticmethod
    def _stream(stream: int, limit: int) -> bytes:
        try:  # from the start: a stream handed over may not be there (it can fail: some can't seek)
            _method(stream, STREAM_SEEK, ctypes.c_int64, wintypes.DWORD, c_void_p)(stream, 0, STREAM_SEEK_SET, None)
        except OSError:
            pass
        read = _method(stream, STREAM_READ, c_void_p, wintypes.ULONG, POINTER(wintypes.ULONG))
        chunks, total, buffer, got = [], 0, ctypes.create_string_buffer(CHUNK), wintypes.ULONG()
        while total <= limit:
            if read(stream, buffer, CHUNK, byref(got)) < 0 or not got.value:
                break
            chunks.append(buffer.raw[: got.value])
            total += got.value
        return b"".join(chunks)[: limit + 1]

    def files(self) -> list[str]:
        """Files on disk (CF_HDROP)."""
        etc, medium = FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL), STGMEDIUM()
        if _method(self.ptr, GET_DATA, POINTER(FORMATETC), POINTER(STGMEDIUM))(self.ptr, byref(etc), byref(medium)) != S_OK:
            return []
        try:
            if medium.tymed != TYMED_HGLOBAL or not medium.handle:
                return []
            names = []
            for i in range(_shell32.DragQueryFileW(medium.handle, 0xFFFFFFFF, None, 0)):
                length = _shell32.DragQueryFileW(medium.handle, i, None, 0)
                name = ctypes.create_unicode_buffer(length + 1)
                if _shell32.DragQueryFileW(medium.handle, i, name, length + 1):
                    names.append(name.value)
            return names
        finally:
            _ole32.ReleaseStgMedium(byref(medium))

    def named(self) -> list[winfiles.Dropped]:
        """Files that aren't on disk, read now."""
        descriptors = self.data(CF_DESCRIPTORS, limit=4 + 1000 * 592)
        if not descriptors:
            return []
        return winfiles.read(winfiles.parse(descriptors), lambda index: self.data(CF_CONTENTS, index))

    def image(self) -> QImage | None:
        for cf in (CF_PNG, CF_DIBV5, CF_DIB):
            raw = self.data(cf) if self.has(cf) else None
            if raw and cf != CF_PNG:
                raw = bmp(raw)
            image = QImage.fromData(raw) if raw else QImage()
            if not image.isNull():
                return image
        return None

    def text(self) -> str | None:
        raw = self.data(CF_UNICODETEXT) if self.has(CF_UNICODETEXT) else None
        text = raw.decode("utf-16-le", errors="replace").split("\0", 1)[0] if raw else ""
        return text or None

    def offers(self) -> bool:
        return any(self.has(cf) for cf in (CF_HDROP, CF_DESCRIPTORS, CF_PNG, CF_DIBV5, CF_DIB, CF_UNICODETEXT))

    def contents(self) -> tuple[str, object] | None:
        """What the ask box takes, best first, as bubble.clipboard_contents says it."""
        if self.has(CF_HDROP):
            files = self.files()
            if files:
                return "files", files
        if self.has(CF_DESCRIPTORS):
            named = self.named()
            if named:
                return "named", named
        image = self.image()
        if image is not None:
            return "image", image
        text = self.text()
        return ("text", text) if text else None


def clipboard_named() -> list[winfiles.Dropped] | None:
    """Files that aren't on disk, on the clipboard (copied out of Outlook or a zip folder), read now; None if
    there are none, or there are files on disk too (Qt reads those)."""
    held = c_void_p()
    try:
        if _ole32.OleGetClipboard(byref(held)) != S_OK or not held.value:
            return None
    except OSError:
        return None
    try:
        data = DataObject(held.value)
        if data.has(CF_HDROP) or not data.has(CF_DESCRIPTORS):
            return None
        return data.named() or None
    finally:
        _release(held.value)


class _Object(ctypes.Structure):
    _fields_ = [("vtable", c_void_p)]


_QueryInterface = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, c_void_p, POINTER(c_void_p))
_Count = ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)
# POINTL comes by value: 8 bytes, passed as one 64-bit number would be.
_DragEnter = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, c_void_p, wintypes.DWORD, ctypes.c_uint64, POINTER(wintypes.DWORD))
_DragOver = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, wintypes.DWORD, ctypes.c_uint64, POINTER(wintypes.DWORD))
_DragLeave = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p)


class DropTarget:
    """Chatmon's own drop target for one window. `wants()` says whether a drop would be taken now (the ask
    box is open for typing); `dropped(kind, payload)` gets what was dropped, just after the drop."""

    def __init__(self, wants: Callable[[], bool], dropped: Callable[[str, object], None]):
        self._wants, self._dropped = wants, dropped
        self._offered = False
        self._refs = 1
        self._callbacks = (
            _QueryInterface(self._query), _Count(self._add_ref), _Count(self._release),
            _DragEnter(self._drag_enter), _DragOver(self._drag_over), _DragLeave(self._drag_leave), _DragEnter(self._drop),
        )
        self._vtable = (c_void_p * len(self._callbacks))(*(ctypes.cast(f, c_void_p) for f in self._callbacks))
        self._object = _Object(ctypes.cast(self._vtable, c_void_p))
        self.ptr = ctypes.addressof(self._object)
        self.hwnd = 0

    def attach(self, hwnd: int) -> bool:
        """Take this window's drops, in place of Qt's drop target; again if the window was made anew."""
        if hwnd == self.hwnd:
            return True
        _ole32.RevokeDragDrop(hwnd)  # Qt's
        self.hwnd = hwnd if _ole32.RegisterDragDrop(hwnd, self.ptr) == S_OK else 0
        return bool(self.hwnd)

    def detach(self) -> None:
        if self.hwnd:
            _ole32.RevokeDragDrop(self.hwnd)
            self.hwnd = 0

    # -- IUnknown: Python keeps the object, whatever the count says

    def _query(self, this, iid, out) -> int:
        if ctypes.string_at(iid, 16) in (IID_IUNKNOWN, IID_IDROPTARGET):
            out[0] = this
            self._refs += 1
            return S_OK
        out[0] = None
        return E_NOINTERFACE

    def _add_ref(self, this) -> int:
        self._refs += 1
        return self._refs

    def _release(self, this) -> int:
        self._refs = max(1, self._refs - 1)
        return self._refs

    # -- IDropTarget

    def _effect(self, effect) -> None:
        effect[0] = DROPEFFECT_COPY if self._offered and effect[0] & DROPEFFECT_COPY and self._wants() else DROPEFFECT_NONE

    def _drag_enter(self, this, data, keys, point, effect) -> int:
        try:
            self._offered = bool(data) and DataObject(data).offers()
            self._effect(effect)
            return S_OK
        except Exception:  # never into Windows' drag loop
            effect[0] = DROPEFFECT_NONE
            return E_UNEXPECTED

    def _drag_over(self, this, keys, point, effect) -> int:
        try:
            self._effect(effect)
            return S_OK
        except Exception:
            effect[0] = DROPEFFECT_NONE
            return E_UNEXPECTED

    def _drag_leave(self, this) -> int:
        self._offered = False
        return S_OK

    def _drop(self, this, data, keys, point, effect) -> int:
        try:
            self._offered = bool(data) and DataObject(data).offers()
            self._effect(effect)
            found = DataObject(data).contents() if effect[0] == DROPEFFECT_COPY else None
            if found is None:
                effect[0] = DROPEFFECT_NONE
            else:  # read: the rest once the drop is over (the program it came from waits for it)
                QTimer.singleShot(0, lambda: self._dropped(*found))
            return S_OK
        except Exception:
            effect[0] = DROPEFFECT_NONE
            return E_UNEXPECTED
        finally:
            self._offered = False
