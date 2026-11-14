"""The session bus through libdbus itself, with ctypes, for what QtDBus can't do from Python.

QtDBus marshals only the types registered with it, and from Python no struct type can be: a call taking an array of
structs, such as the GlobalShortcuts portal's BindShortcuts(o, a(sa{sv}), s, a{sv}), makes libdbus abort the process
("Writing an element of type struct, but the expected type here is array"). libdbus takes any signature. It's the
library QtDBus loads, so it's there wherever QtDBus works, and every Linux desktop has it.

A Bus is a private connection of its own, used from one thread: calls block that thread (never the screen's), and
signals are read with next_message(). Imports anywhere; the library is loaded when a Bus is made.
https://dbus.freedesktop.org/doc/api/html/group__DBusMessage.html
https://dbus.freedesktop.org/doc/dbus-specification.html#type-system"""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Any

SESSION = 0  # DBUS_BUS_SESSION
METHOD_CALL, METHOD_RETURN, ERROR, SIGNAL = 1, 2, 3, 4
NAME_PRIMARY_OWNER = 1
NAME_DO_NOT_QUEUE = 0x4
BASIC = {"y": ctypes.c_ubyte, "b": ctypes.c_uint32, "n": ctypes.c_int16, "q": ctypes.c_uint16, "i": ctypes.c_int32,
         "u": ctypes.c_uint32, "x": ctypes.c_int64, "t": ctypes.c_uint64, "d": ctypes.c_double, "h": ctypes.c_int32}
STRINGS = "sog"  # string, object path, signature
CONTAINER = {"a": ord("a"), "(": ord("r"), "{": ord("e"), "v": ord("v")}  # DBUS_TYPE_ARRAY, STRUCT, DICT_ENTRY, VARIANT


class ObjectPath(str):
    """A D-Bus object path ('o'), where a plain str would be a string ('s')."""


class Variant:
    """A value in a variant with the type given, where guessing from Python's type would be wrong."""

    def __init__(self, signature: str, value: Any):
        self.signature, self.value = signature, value

    def __repr__(self) -> str:
        return f"Variant({self.signature!r}, {self.value!r})"


class Failure(Exception):
    """A D-Bus error reply, or a failure to reach the bus: `name` is the error's name."""

    def __init__(self, name: str, message: str = ""):
        super().__init__(f"{name}: {message}" if message else name)
        self.name, self.message = name, message


class _Error(ctypes.Structure):  # DBusError
    _fields_ = [("name", ctypes.c_char_p), ("message", ctypes.c_char_p), ("dummy", ctypes.c_uint), ("padding", ctypes.c_void_p)]


class _Iter(ctypes.Structure):  # DBusMessageIter: opaque, and smaller than this in every libdbus
    _fields_ = [("opaque", ctypes.c_void_p * 16)]


def complete_types(signature: str) -> list[str]:
    """A signature split into its complete types: "oa(sa{sv})sa{sv}" -> ["o", "a(sa{sv})", "s", "a{sv}"]."""
    types, i = [], 0
    while i < len(signature):
        end = _type_end(signature, i)
        types.append(signature[i:end])
        i = end
    return types


def _type_end(signature: str, i: int) -> int:
    if i >= len(signature):
        raise ValueError(f"Signature {signature!r} ends too soon.")
    c = signature[i]
    if c == "a":
        return _type_end(signature, i + 1)
    if c in "({":
        close = ")" if c == "(" else "}"
        i += 1
        while signature[i:i + 1] != close:
            i = _type_end(signature, i)
        return i + 1
    if c in BASIC or c in STRINGS or c == "v":
        return i + 1
    raise ValueError(f"Signature {signature!r} has a type D-Bus hasn't: {c!r}.")


def guess(value: Any) -> str:
    """The signature for a variant's value, from its Python type."""
    if isinstance(value, Variant):
        return value.signature
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "i" if -(2 ** 31) <= value < 2 ** 31 else "x"
    if isinstance(value, float):
        return "d"
    if isinstance(value, ObjectPath):
        return "o"
    if isinstance(value, str):
        return "s"
    if isinstance(value, bytes):
        return "ay"
    if isinstance(value, dict):
        return "a{sv}"
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return "as"
    raise TypeError(f"Can't tell which D-Bus type {value!r} is: give it as a Variant.")


_lib = None


def lib():
    """libdbus, with the prototype of every function used here."""
    global _lib
    if _lib is not None:
        return _lib
    dbus = ctypes.cdll.LoadLibrary(ctypes.util.find_library("dbus-1") or "libdbus-1.so.3")
    vp, cp, b, i, u = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32
    err, it = ctypes.POINTER(_Error), ctypes.POINTER(_Iter)
    for name, restype, argtypes in (
        ("dbus_threads_init_default", b, []),
        ("dbus_error_init", None, [err]), ("dbus_error_free", None, [err]),
        ("dbus_bus_get_private", vp, [i, err]),
        ("dbus_connection_set_exit_on_disconnect", None, [vp, b]),
        ("dbus_connection_close", None, [vp]), ("dbus_connection_unref", None, [vp]),
        ("dbus_bus_get_unique_name", cp, [vp]),
        ("dbus_bus_request_name", i, [vp, cp, u, err]),
        ("dbus_bus_add_match", None, [vp, cp, err]),
        ("dbus_message_new_method_call", vp, [cp, cp, cp, cp]),
        ("dbus_message_new_signal", vp, [cp, cp, cp]),
        ("dbus_message_new_method_return", vp, [vp]),
        ("dbus_message_new_error", vp, [vp, cp, cp]),
        ("dbus_message_unref", None, [vp]),
        ("dbus_message_iter_init_append", None, [vp, it]),
        ("dbus_message_iter_append_basic", b, [it, i, vp]),
        ("dbus_message_iter_open_container", b, [it, i, cp, it]),
        ("dbus_message_iter_close_container", b, [it, it]),
        ("dbus_message_iter_init", b, [vp, it]),
        ("dbus_message_iter_get_arg_type", i, [it]),
        ("dbus_message_iter_get_basic", None, [it, vp]),
        ("dbus_message_iter_recurse", None, [it, it]),
        ("dbus_message_iter_next", b, [it]),
        ("dbus_message_iter_get_signature", vp, [it]),
        ("dbus_free", None, [vp]),
        ("dbus_connection_send", b, [vp, vp, ctypes.POINTER(u)]),
        ("dbus_connection_send_with_reply_and_block", vp, [vp, vp, i, err]),
        ("dbus_connection_flush", None, [vp]),
        ("dbus_connection_read_write", b, [vp, i]),
        ("dbus_connection_pop_message", vp, [vp]),
        ("dbus_message_get_type", i, [vp]),
        ("dbus_message_get_path", cp, [vp]), ("dbus_message_get_interface", cp, [vp]),
        ("dbus_message_get_member", cp, [vp]), ("dbus_message_get_sender", cp, [vp]),
        ("dbus_message_get_signature", cp, [vp]), ("dbus_message_get_error_name", cp, [vp]),
    ):
        function = getattr(dbus, name)
        function.restype, function.argtypes = restype, argtypes
    dbus.dbus_threads_init_default()
    _lib = dbus
    return dbus


def _text(raw: bytes | None) -> str:
    return raw.decode("utf-8", "replace") if raw else ""


def append(dbus, it: _Iter, signature: str, value: Any) -> None:
    """Write one value of one complete type."""
    c = signature[0]
    if c in BASIC:
        cell = BASIC[c](int(bool(value)) if c == "b" else value)
        if not dbus.dbus_message_iter_append_basic(ctypes.byref(it), ord(c), ctypes.byref(cell)):
            raise MemoryError
    elif c in STRINGS:
        cell = ctypes.c_char_p(str(value).encode("utf-8"))
        if not dbus.dbus_message_iter_append_basic(ctypes.byref(it), ord(c), ctypes.byref(cell)):
            raise ValueError(f"D-Bus refused {value!r} as {signature!r}.")  # an invalid object path, say
    elif c == "v":
        inner = value.signature if isinstance(value, Variant) else guess(value)
        _container(dbus, it, "v", inner.encode(), lambda sub: append(dbus, sub, inner, value.value if isinstance(value, Variant) else value))
    elif c == "a":
        element = signature[1:]
        items = list(value.items()) if element.startswith("{") else list(value)
        _container(dbus, it, "a", element.encode(), lambda sub: [append(dbus, sub, element, item) for item in items])
    elif c in "({":
        fields = complete_types(signature[1:-1])
        values = list(value)
        if len(values) != len(fields):
            raise ValueError(f"{value!r} doesn't fit {signature!r}.")
        _container(dbus, it, c, None, lambda sub: [append(dbus, sub, f, v) for f, v in zip(fields, values, strict=True)])
    else:
        raise ValueError(f"Can't write D-Bus type {signature!r}.")


def _container(dbus, it: _Iter, kind: str, contained: bytes | None, fill) -> None:
    sub = _Iter()
    if not dbus.dbus_message_iter_open_container(ctypes.byref(it), CONTAINER[kind], contained, ctypes.byref(sub)):
        raise MemoryError
    fill(sub)
    if not dbus.dbus_message_iter_close_container(ctypes.byref(it), ctypes.byref(sub)):
        raise MemoryError


def read(dbus, it: _Iter) -> Any:
    """Read the value at the iterator, as Python's: a struct a tuple, a dictionary a dict, a variant its value."""
    kind = chr(dbus.dbus_message_iter_get_arg_type(ctypes.byref(it)))
    if kind in BASIC:
        cell = ctypes.c_uint64()  # DBusBasicValue: 8 bytes
        dbus.dbus_message_iter_get_basic(ctypes.byref(it), ctypes.byref(cell))
        value = ctypes.cast(ctypes.byref(cell), ctypes.POINTER(BASIC[kind])).contents.value
        return bool(value) if kind == "b" else value
    if kind in STRINGS:
        cell = ctypes.c_char_p()
        dbus.dbus_message_iter_get_basic(ctypes.byref(it), ctypes.byref(cell))
        text = _text(cell.value)
        return ObjectPath(text) if kind == "o" else text
    sub = _Iter()
    dbus.dbus_message_iter_recurse(ctypes.byref(it), ctypes.byref(sub))
    if kind == "v":
        return read(dbus, sub)
    if kind in "r(":
        return tuple(_read_all(dbus, sub))
    if kind == "a":
        if chr(dbus.dbus_message_iter_get_arg_type(ctypes.byref(sub))) == "e":
            entries = {}
            for _ in _each(dbus, sub):
                entry = _Iter()
                dbus.dbus_message_iter_recurse(ctypes.byref(sub), ctypes.byref(entry))
                key = read(dbus, entry)
                dbus.dbus_message_iter_next(ctypes.byref(entry))
                entries[key] = read(dbus, entry)
            return entries
        return _read_all(dbus, sub)
    raise ValueError(f"Can't read D-Bus type {kind!r}.")


def _each(dbus, it: _Iter):
    """Step through a container's values (an empty one has none)."""
    while dbus.dbus_message_iter_get_arg_type(ctypes.byref(it)) != 0:  # DBUS_TYPE_INVALID: the end
        yield it
        dbus.dbus_message_iter_next(ctypes.byref(it))


def _read_all(dbus, it: _Iter) -> list:
    return [read(dbus, i) for i in _each(dbus, it)]


class Message:
    """A message off the bus, read: `kind` (METHOD_CALL, SIGNAL...), where it's from and to, and its `args`."""

    def __init__(self, dbus, raw: int):
        self._dbus, self.raw = dbus, raw
        self.kind = dbus.dbus_message_get_type(raw)
        self.path = _text(dbus.dbus_message_get_path(raw))
        self.interface = _text(dbus.dbus_message_get_interface(raw))
        self.member = _text(dbus.dbus_message_get_member(raw))
        self.sender = _text(dbus.dbus_message_get_sender(raw))
        self.signature = _text(dbus.dbus_message_get_signature(raw))
        self.error = _text(dbus.dbus_message_get_error_name(raw))
        it = _Iter()
        self.args = _read_all(dbus, it) if dbus.dbus_message_iter_init(raw, ctypes.byref(it)) else []

    def free(self) -> None:
        if self.raw:
            self._dbus.dbus_message_unref(self.raw)
            self.raw = None

    def __del__(self) -> None:
        self.free()


class Bus:
    """A private connection to the session bus, for one thread."""

    def __init__(self) -> None:
        self._dbus = lib()
        error = _Error()
        self._dbus.dbus_error_init(ctypes.byref(error))
        self._conn = self._dbus.dbus_bus_get_private(SESSION, ctypes.byref(error))
        if not self._conn:
            self._fail(error, "org.freedesktop.DBus.Error.NoServer")
        self._dbus.dbus_connection_set_exit_on_disconnect(self._conn, 0)  # never take Chatmon down with it
        self.unique_name = _text(self._dbus.dbus_bus_get_unique_name(self._conn))

    def _fail(self, error: _Error, fallback: str):
        name, message = _text(error.name) or fallback, _text(error.message)
        self._dbus.dbus_error_free(ctypes.byref(error))
        raise Failure(name, message)

    def _message(self, raw: int, signature: str, args) -> int:
        if not raw:
            raise MemoryError
        types = complete_types(signature)
        if len(types) != len(args):
            self._dbus.dbus_message_unref(raw)
            raise ValueError(f"{len(args)} arguments for signature {signature!r}.")
        it = _Iter()
        self._dbus.dbus_message_iter_init_append(raw, ctypes.byref(it))
        try:
            for kind, value in zip(types, args, strict=True):
                append(self._dbus, it, kind, value)
        except Exception:
            self._dbus.dbus_message_unref(raw)
            raise
        return raw

    def call(self, destination: str, path: str, interface: str, method: str, signature: str = "", args=(), timeout_ms: int = 5000) -> list:
        """Call a method and wait for its reply's arguments; Failure for an error reply (or none in time)."""
        raw = self._message(self._dbus.dbus_message_new_method_call(destination.encode(), path.encode(), interface.encode(), method.encode()),
                            signature, args)
        error = _Error()
        self._dbus.dbus_error_init(ctypes.byref(error))
        try:
            reply = self._dbus.dbus_connection_send_with_reply_and_block(self._conn, raw, timeout_ms, ctypes.byref(error))
        finally:
            self._dbus.dbus_message_unref(raw)
        if not reply:
            self._fail(error, "org.freedesktop.DBus.Error.Failed")
        message = Message(self._dbus, reply)
        try:
            return message.args
        finally:
            message.free()

    def _send(self, raw: int) -> None:
        try:
            if not self._dbus.dbus_connection_send(self._conn, raw, None):
                raise MemoryError
            self._dbus.dbus_connection_flush(self._conn)
        finally:
            self._dbus.dbus_message_unref(raw)

    def emit(self, path: str, interface: str, member: str, signature: str = "", args=()) -> None:
        self._send(self._message(self._dbus.dbus_message_new_signal(path.encode(), interface.encode(), member.encode()), signature, args))

    def reply(self, call: Message, signature: str = "", args=()) -> None:
        self._send(self._message(self._dbus.dbus_message_new_method_return(call.raw), signature, args))

    def reply_error(self, call: Message, name: str, text: str = "") -> None:
        self._send(self._message(self._dbus.dbus_message_new_error(call.raw, name.encode(), text.encode()), "", ()))

    def add_match(self, rule: str) -> None:
        error = _Error()
        self._dbus.dbus_error_init(ctypes.byref(error))
        self._dbus.dbus_bus_add_match(self._conn, rule.encode(), ctypes.byref(error))
        if error.name:
            self._fail(error, "org.freedesktop.DBus.Error.MatchRuleInvalid")

    def request_name(self, name: str) -> bool:
        error = _Error()
        self._dbus.dbus_error_init(ctypes.byref(error))
        got = self._dbus.dbus_bus_request_name(self._conn, name.encode(), NAME_DO_NOT_QUEUE, ctypes.byref(error))
        if got < 0:
            self._fail(error, "org.freedesktop.DBus.Error.Failed")
        return got == NAME_PRIMARY_OWNER

    def next_message(self, timeout_ms: int) -> Message | None:
        """The next message for this connection, waiting up to `timeout_ms`; None if none came. ConnectionError
        once the bus is gone."""
        raw = self._dbus.dbus_connection_pop_message(self._conn)
        if not raw:
            if not self._dbus.dbus_connection_read_write(self._conn, timeout_ms):
                raise ConnectionError("The session bus went away.")
            raw = self._dbus.dbus_connection_pop_message(self._conn)
        return Message(self._dbus, raw) if raw else None

    def close(self) -> None:
        if self._conn:
            self._dbus.dbus_connection_close(self._conn)
            self._dbus.dbus_connection_unref(self._conn)
            self._conn = None
