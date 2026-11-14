"""The keyboard, for the ask box on the Wayland overlay.

A Wayland client reads the keyboard itself: the compositor sends the keymap
(the user's layout) and raw key codes, and libxkbcommon, which every Wayland
desktop has, turns them into characters, with modifiers, dead keys and compose
sequences. This wraps the few libxkbcommon calls that takes, through ctypes,
and turns keys into what Qt's widgets expect.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from dataclasses import dataclass

from PyQt6.QtCore import Qt

EVDEV_OFFSET = 8  # Wayland sends evdev codes; XKB key codes are 8 higher
FORMAT_TEXT_V1 = 1
MODS_LATCHED, MODS_LOCKED, MODS_EFFECTIVE = 1 << 1, 1 << 2, 1 << 3
LATIN1 = range(0x20, 0x100)  # keysyms that are Latin-1 characters: the ones shortcuts are made of
COMPOSE_COMPOSING, COMPOSE_COMPOSED, COMPOSE_CANCELLED = 1, 2, 3

# Keysyms that aren't characters, and the Qt keys they are.
SPECIAL = {
    0xFF08: Qt.Key.Key_Backspace,
    0xFF09: Qt.Key.Key_Tab,
    0xFE20: Qt.Key.Key_Backtab,  # ISO_Left_Tab: Shift+Tab
    0xFF0D: Qt.Key.Key_Return,
    0xFF1B: Qt.Key.Key_Escape,
    0xFFFF: Qt.Key.Key_Delete,
    0xFF50: Qt.Key.Key_Home,
    0xFF51: Qt.Key.Key_Left,
    0xFF52: Qt.Key.Key_Up,
    0xFF53: Qt.Key.Key_Right,
    0xFF54: Qt.Key.Key_Down,
    0xFF55: Qt.Key.Key_PageUp,
    0xFF56: Qt.Key.Key_PageDown,
    0xFF57: Qt.Key.Key_End,
    0xFF63: Qt.Key.Key_Insert,
    0xFF67: Qt.Key.Key_Menu,
    0xFF8D: Qt.Key.Key_Enter,
    0xFF95: Qt.Key.Key_Home,
    0xFF96: Qt.Key.Key_Left,
    0xFF97: Qt.Key.Key_Up,
    0xFF98: Qt.Key.Key_Right,
    0xFF99: Qt.Key.Key_Down,
    0xFF9A: Qt.Key.Key_PageUp,
    0xFF9B: Qt.Key.Key_PageDown,
    0xFF9C: Qt.Key.Key_End,
    0xFF9E: Qt.Key.Key_Insert,
    0xFF9F: Qt.Key.Key_Delete,
    0xFFE1: Qt.Key.Key_Shift,
    0xFFE2: Qt.Key.Key_Shift,
    0xFFE3: Qt.Key.Key_Control,
    0xFFE4: Qt.Key.Key_Control,
    0xFFE5: Qt.Key.Key_CapsLock,
    0xFFE9: Qt.Key.Key_Alt,
    0xFFEA: Qt.Key.Key_Alt,
    0xFFEB: Qt.Key.Key_Meta,
    0xFFEC: Qt.Key.Key_Meta,
    0xFE03: Qt.Key.Key_AltGr,  # ISO_Level3_Shift
}
SPECIAL.update({0xFFBE + i: Qt.Key(Qt.Key.Key_F1.value + i) for i in range(12)})  # F1..F12
KEYPAD = range(0xFF80, 0xFFBA)  # KP_* keysyms


def library() -> ctypes.CDLL | None:
    name = ctypes.util.find_library("xkbcommon") or "libxkbcommon.so.0"
    try:
        lib = ctypes.CDLL(name)
    except OSError:
        return None
    p, u32, i, s = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_char_p
    for fn, res, args in (
        ("xkb_context_new", p, [i]),
        ("xkb_context_unref", None, [p]),
        ("xkb_keymap_new_from_string", p, [p, s, i, i]),
        ("xkb_keymap_unref", None, [p]),
        ("xkb_keymap_key_repeats", i, [p, u32]),
        ("xkb_state_new", p, [p]),
        ("xkb_state_unref", None, [p]),
        ("xkb_state_update_mask", i, [p, u32, u32, u32, u32, u32, u32]),
        ("xkb_state_key_get_one_sym", u32, [p, u32]),
        ("xkb_state_key_get_utf8", i, [p, u32, s, ctypes.c_size_t]),
        ("xkb_state_mod_name_is_active", i, [p, s, i]),
        ("xkb_keysym_to_utf8", i, [u32, s, ctypes.c_size_t]),
        ("xkb_compose_table_new_from_locale", p, [p, s, i]),
        ("xkb_compose_table_unref", None, [p]),
        ("xkb_compose_state_new", p, [p, i]),
        ("xkb_compose_state_unref", None, [p]),
        ("xkb_compose_state_feed", i, [p, u32]),
        ("xkb_compose_state_reset", None, [p]),
        ("xkb_compose_state_get_status", i, [p]),
        ("xkb_compose_state_get_utf8", i, [p, s, ctypes.c_size_t]),
        ("xkb_compose_state_get_one_sym", u32, [p]),
    ):
        f = getattr(lib, fn)
        f.restype, f.argtypes = res, args
    # What finding a key's Latin symbol takes (Keyboard._latin_sym); a libxkbcommon older than 0.4 lacks some,
    # and shortcuts then work as they did before, on Latin layouts only.
    for fn, res, args in (
        ("xkb_keymap_num_layouts_for_key", u32, [p, u32]),
        ("xkb_keymap_key_get_syms_by_level", i, [p, u32, u32, u32, ctypes.POINTER(ctypes.POINTER(u32))]),
        ("xkb_keymap_min_keycode", u32, [p]),
        ("xkb_keymap_max_keycode", u32, [p]),
        ("xkb_state_key_get_layout", u32, [p, u32]),
        ("xkb_state_key_get_level", u32, [p, u32, u32]),
        ("xkb_state_serialize_mods", u32, [p, i]),
    ):
        try:
            f = getattr(lib, fn)
        except AttributeError:
            continue
        f.restype, f.argtypes = res, args
    return lib


LATIN_CALLS = (
    "xkb_keymap_num_layouts_for_key", "xkb_keymap_key_get_syms_by_level", "xkb_keymap_min_keycode",
    "xkb_keymap_max_keycode", "xkb_state_key_get_layout", "xkb_state_key_get_level", "xkb_state_serialize_mods",
)


def _locale(env=os.environ) -> str:
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        if env.get(var):
            return env[var]
    return "C"


@dataclass
class Key:
    key: Qt.Key | int
    text: str
    modifiers: Qt.KeyboardModifier


class Keyboard:
    """One keymap and its state: keys in, Qt keys and text out."""

    def __init__(self, lib: ctypes.CDLL, keymap: str):
        self.lib = lib
        self._ctx = lib.xkb_context_new(0)
        self._keymap = lib.xkb_keymap_new_from_string(self._ctx, keymap.encode(), FORMAT_TEXT_V1, 0) if self._ctx else None
        if not self._keymap:
            self.close()
            raise ValueError("couldn't read the keymap")
        self._state = lib.xkb_state_new(self._keymap)
        self._latin = all(hasattr(lib, fn) for fn in LATIN_CALLS)
        self._compose_table = lib.xkb_compose_table_new_from_locale(self._ctx, _locale().encode(), 0)
        self._compose = lib.xkb_compose_state_new(self._compose_table, 0) if self._compose_table else None

    def close(self) -> None:
        lib = self.lib
        for attr, unref in (
            ("_compose", lib.xkb_compose_state_unref),
            ("_compose_table", lib.xkb_compose_table_unref),
            ("_state", lib.xkb_state_unref),
            ("_keymap", lib.xkb_keymap_unref),
            ("_ctx", lib.xkb_context_unref),
        ):
            if getattr(self, attr, None):
                unref(getattr(self, attr))
                setattr(self, attr, None)

    def set_modifiers(self, depressed: int, latched: int, locked: int, group: int) -> None:
        self.lib.xkb_state_update_mask(self._state, depressed, latched, locked, 0, 0, group)

    def modifiers(self) -> Qt.KeyboardModifier:
        mods = Qt.KeyboardModifier.NoModifier
        for name, flag in (
            (b"Shift", Qt.KeyboardModifier.ShiftModifier),
            (b"Control", Qt.KeyboardModifier.ControlModifier),
            (b"Mod1", Qt.KeyboardModifier.AltModifier),
            (b"Mod4", Qt.KeyboardModifier.MetaModifier),
        ):
            if self.lib.xkb_state_mod_name_is_active(self._state, name, MODS_EFFECTIVE) > 0:
                mods |= flag
        return mods

    def repeats(self, code: int) -> bool:
        return bool(self.lib.xkb_keymap_key_repeats(self._keymap, code + EVDEV_OFFSET))

    def press(self, code: int) -> Key | None:
        """A key went down (an evdev code); None while it's part of a compose sequence."""
        xkb_code = code + EVDEV_OFFSET
        sym = self.lib.xkb_state_key_get_one_sym(self._state, xkb_code)
        text = self._utf8(self.lib.xkb_state_key_get_utf8, self._state, xkb_code)
        if self._compose is not None and self.lib.xkb_compose_state_feed(self._compose, sym) == 1:
            status = self.lib.xkb_compose_state_get_status(self._compose)
            if status == COMPOSE_COMPOSING:
                return None
            if status == COMPOSE_CANCELLED:
                self.lib.xkb_compose_state_reset(self._compose)
                return None
            if status == COMPOSE_COMPOSED:
                text = self._utf8(self.lib.xkb_compose_state_get_utf8, self._compose)
                sym = self.lib.xkb_compose_state_get_one_sym(self._compose) or sym
                self.lib.xkb_compose_state_reset(self._compose)
        return self._key(sym, text, xkb_code)

    def release(self, code: int) -> Key:
        xkb_code = code + EVDEV_OFFSET
        sym = self.lib.xkb_state_key_get_one_sym(self._state, xkb_code)
        return self._key(sym, self._utf8(self.lib.xkb_state_key_get_utf8, self._state, xkb_code), xkb_code)

    def _key(self, sym: int, text: str, xkb_code: int) -> Key:
        mods = self.modifiers()
        # Ctrl or Alt with a letter of a non-Latin layout (Cyrillic, Greek, Hebrew...) is a shortcut, and
        # shortcuts are Latin letters: Ctrl+V is the key that is V in another layout you have, as in Qt's own
        # windows. The text stays what the layout types.
        if (
            mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            and sym not in LATIN1 and sym not in SPECIAL and sym not in KEYPAD
        ):
            sym = self._latin_sym(xkb_code) or sym
        if sym in KEYPAD:
            mods |= Qt.KeyboardModifier.KeypadModifier
        if sym in SPECIAL:
            key = SPECIAL[sym]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                text = "\r"
            elif key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                text = "\t"
            elif key == Qt.Key.Key_Backspace:
                text = "\b"
            elif key == Qt.Key.Key_Escape:
                text = "\x1b"
            elif key == Qt.Key.Key_Delete:
                text = "\x7f"
            else:
                text = ""
            return Key(key, text, mods)
        # A character: Qt names the key by its character, upper case (Ctrl+A is Key_A).
        char = self._utf8(self.lib.xkb_keysym_to_utf8, sym) or text
        key = ord(char.upper()[0]) if len(char.upper()) == 1 else (ord(char[0]) if char else 0)
        return Key(key, text, mods)

    def _latin_sym(self, xkb_code: int) -> int:
        """The key's Latin-1 symbol in the first other layout that has one at the same level, or 0. As Qt's
        QXkbCommon::lookupLatinKeysym: not if a key of an earlier layout already types that symbol (with us
        Dvorak, ru and us, Ctrl+Q is Dvorak's Q, not the key that is Q in the last layout)."""
        if not self._latin:
            return 0
        lib, keymap, state = self.lib, self._keymap, self._state
        current = lib.xkb_state_key_get_layout(state, xkb_code)
        syms = ctypes.POINTER(ctypes.c_uint32)()
        found, found_in = 0, 0
        for layout in range(lib.xkb_keymap_num_layouts_for_key(keymap, xkb_code)):
            if layout == current:
                continue
            level = lib.xkb_state_key_get_level(state, xkb_code, layout)
            if lib.xkb_keymap_key_get_syms_by_level(keymap, xkb_code, layout, level, ctypes.byref(syms)) == 1 and syms[0] in LATIN1:
                found, found_in = syms[0], layout
                break
        if not found or not found_in:
            return found
        latched = lib.xkb_state_serialize_mods(state, MODS_LATCHED)
        locked = lib.xkb_state_serialize_mods(state, MODS_LOCKED)
        query = lib.xkb_state_new(keymap)
        try:
            first, last = lib.xkb_keymap_min_keycode(keymap), lib.xkb_keymap_max_keycode(keymap)
            for earlier in range(found_in):
                lib.xkb_state_update_mask(query, 0, latched, locked, 0, 0, earlier)
                if any(lib.xkb_state_key_get_one_sym(query, other) == found for other in range(first, last)):
                    return 0
        finally:
            lib.xkb_state_unref(query)
        return found

    @staticmethod
    def _utf8(fn, *args) -> str:
        buf = ctypes.create_string_buffer(64)
        n = fn(*args, buf, len(buf))
        # keysym_to_utf8 counts the terminating NUL, the others don't
        return buf.raw[:n].decode("utf-8", errors="replace").rstrip("\0") if n > 0 else ""


class _RuleNames(ctypes.Structure):
    _fields_ = [(f, ctypes.c_char_p) for f in ("rules", "model", "layout", "variant", "options")]


def keymap_from_names(lib: ctypes.CDLL, layout: str = "us", variant: str = "") -> str:
    """A keymap compiled from layout names, as text (what a compositor would send)."""
    lib.xkb_keymap_new_from_names.restype = ctypes.c_void_p
    lib.xkb_keymap_new_from_names.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RuleNames), ctypes.c_int]
    lib.xkb_keymap_get_as_string.restype = ctypes.c_void_p
    lib.xkb_keymap_get_as_string.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]
    ctx = lib.xkb_context_new(0)
    names = _RuleNames(None, None, layout.encode(), variant.encode() or None, None)
    keymap = lib.xkb_keymap_new_from_names(ctx, ctypes.byref(names), 0)
    if not keymap:
        lib.xkb_context_unref(ctx)
        raise ValueError(f"no keymap for {layout!r}")
    raw = lib.xkb_keymap_get_as_string(keymap, FORMAT_TEXT_V1)
    text = ctypes.string_at(raw).decode()
    libc.free(raw)
    lib.xkb_keymap_unref(keymap)
    lib.xkb_context_unref(ctx)
    return text
