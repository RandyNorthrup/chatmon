"""The overlay's keyboard: keymaps in, Qt keys and text out (needs libxkbcommon)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402

from chatmon import xkb  # noqa: E402

LIB = xkb.library()
pytestmark = pytest.mark.skipif(LIB is None, reason="libxkbcommon isn't installed")

# evdev key codes
Q, Y, A, APOSTROPHE, E, ENTER, BACKSPACE, ESC, LEFT, KP_1 = 16, 21, 30, 40, 18, 28, 14, 1, 105, 79
SHIFT, CTRL = 1, 4  # modifier masks in these keymaps


def board(layout="us", variant=""):
    return xkb.Keyboard(LIB, xkb.keymap_from_names(LIB, layout, variant))


def test_characters_follow_the_layout():
    us, de, fr = board("us"), board("de"), board("fr")
    assert us.press(Y).text == "y" and de.press(Y).text == "z"
    assert us.press(Q).text == "q" and fr.press(Q).text == "a"  # AZERTY
    for kb in (us, de, fr):
        kb.close()


def test_modifiers():
    kb = board()
    kb.set_modifiers(SHIFT, 0, 0, 0)
    key = kb.press(A)
    assert (key.key, key.text, key.modifiers) == (Qt.Key.Key_A.value, "A", Qt.KeyboardModifier.ShiftModifier)
    kb.set_modifiers(CTRL, 0, 0, 0)
    key = kb.press(A)
    assert key.key == Qt.Key.Key_A.value and key.modifiers == Qt.KeyboardModifier.ControlModifier  # Ctrl+A selects all
    kb.close()


def test_keys_that_arent_characters():
    kb = board()
    assert kb.press(ENTER).key == Qt.Key.Key_Return
    assert kb.press(BACKSPACE).key == Qt.Key.Key_Backspace
    assert kb.press(ESC).key == Qt.Key.Key_Escape
    assert kb.press(LEFT).key == Qt.Key.Key_Left and kb.press(LEFT).text == ""
    assert kb.repeats(A) and not kb.repeats(42)  # letters repeat, Shift doesn't
    kb.close()


def test_dead_keys_compose():
    kb = board("us", "intl")
    assert kb.press(APOSTROPHE) is None  # waiting for the letter
    assert kb.press(E).text == "é"
    kb.close()


def test_the_keypad_says_so():
    kb = board()
    kb.set_modifiers(0, 0, 16, 0)  # Num Lock (Mod2) locked
    key = kb.press(KP_1)
    assert key.text == "1" and key.modifiers & Qt.KeyboardModifier.KeypadModifier
    kb.close()


# The keys that are V, C, X, A, Z on a US keyboard (evdev codes), and Alt's modifier mask in these keymaps.
V, C, X, Z = 47, 46, 45, 44
ALT = 8
RUSSIAN = 1  # the layout index of "ru" in a "us,ru" keymap


def test_shortcuts_on_a_russian_layout_are_the_latin_keys():
    kb = board("us,ru")
    kb.set_modifiers(0, 0, 0, RUSSIAN)
    assert kb.press(V).text == "м"  # typing is Russian
    for code, qt in ((V, Qt.Key.Key_V), (C, Qt.Key.Key_C), (X, Qt.Key.Key_X), (A, Qt.Key.Key_A), (Z, Qt.Key.Key_Z)):
        kb.set_modifiers(CTRL, 0, 0, RUSSIAN)
        key = kb.press(code)
        assert (key.key, key.modifiers) == (qt.value, Qt.KeyboardModifier.ControlModifier), qt
        assert kb.release(code).key == qt.value
    kb.set_modifiers(ALT, 0, 0, RUSSIAN)
    assert kb.press(V).key == Qt.Key.Key_V.value  # Alt too: a menu's accelerator
    kb.set_modifiers(SHIFT | CTRL, 0, 0, RUSSIAN)
    assert kb.press(Z).key == Qt.Key.Key_Z.value  # Ctrl+Shift+Z, redo
    kb.set_modifiers(0, 0, 0, RUSSIAN)
    assert kb.press(V).key == ord("М")  # without Ctrl or Alt it's a Russian letter
    kb.close()


def test_a_layout_with_no_latin_partner_keeps_its_own_symbol():
    kb = board("ru")
    kb.set_modifiers(CTRL, 0, 0, 0)
    assert kb.press(V).key == ord("М")
    kb.close()


def test_latin_layouts_are_left_alone():
    kb = board("us,ru")
    kb.set_modifiers(CTRL, 0, 0, 0)  # US active
    assert kb.press(V).key == Qt.Key.Key_V.value
    kb.close()
    kb = board("de")
    kb.set_modifiers(CTRL, 0, 0, 0)
    assert kb.press(Y).key == Qt.Key.Key_Z.value  # a German Z is Ctrl+Z where it is, not where the US has it
    kb.close()


def test_the_latin_symbol_comes_from_the_first_layout_that_has_one():
    """With Dvorak first, Ctrl and the key that is Dvorak's Q is Ctrl+Q, whatever the US layout after it says."""
    kb = board("us,ru,us", "dvorak,,")
    kb.set_modifiers(CTRL, 0, 0, RUSSIAN)
    assert kb.press(X).key == Qt.Key.Key_Q.value  # Dvorak has Q where the US has X
    kb.close()
