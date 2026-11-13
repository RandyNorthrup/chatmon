"""macOS: what Chatmon tells AppKit itself. Run where Qt's cocoa platform is (CI's macOS runner has a desktop
session): `QT_QPA_PLATFORM=cocoa python -m pytest tests/test_macnative.py`."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


@pytest.fixture
def cocoa(qapp):
    from PyQt6.QtGui import QGuiApplication

    if QGuiApplication.platformName() != "cocoa":
        pytest.skip("needs Qt's cocoa platform (QT_QPA_PLATFORM=cocoa)")
    return qapp


def test_the_stage_floats_on_every_space_but_not_in_full_screen_apps(cocoa):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget

    from chatmon import clickthrough, macnative

    window = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
    window.resize(200, 200)
    window.show()
    cocoa.processEvents()
    assert macnative.float_everywhere(window)
    toggle = clickthrough.for_window(window)
    assert type(toggle) is clickthrough.MacPointerToggle
    for i in range(50):  # the pointer crossing the chatmon: the window's Spaces must survive it
        toggle._accept(i % 2 == 0)
    behavior = macnative.collection_behavior(window)
    assert behavior & macnative.OVERLAY == macnative.OVERLAY
    assert not behavior & (macnative.FULL_SCREEN_AUXILIARY | macnative.FULL_SCREEN_PRIMARY | macnative.MOVE_TO_ACTIVE_SPACE)
    macnative.activate()  # never raises
    window.close()


def _until(app, check, seconds: float) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if check():
            return True
        time.sleep(0.2)
    return False


def test_a_full_screen_app_over_the_chatmon_is_seen(cocoa):
    """Another app goes full screen on the chatmon's screen, as a real full-screen Space (macOS animates into
    it): the stage is seen to be under it, and out from under it again once that app has gone."""
    import os
    import subprocess

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QWidget

    from chatmon import macnative

    stage = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
    stage.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    stage.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    stage.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # as the stage: shown while another app is active
    stage.setGeometry(QGuiApplication.primaryScreen().geometry())
    stage.show()
    cocoa.processEvents()
    assert macnative.float_everywhere(stage)
    view = int(stage.winId())
    assert not macnative.full_screen_over(view) and not macnative.full_screen_over(0)
    script = ("from PyQt6.QtCore import QTimer\nfrom PyQt6.QtWidgets import QApplication, QLabel\napp = QApplication([])\n"
              "w = QLabel('A full-screen app')\nw.showFullScreen()\nQTimer.singleShot(30000, app.quit)\napp.exec()\n")
    other = subprocess.Popen([sys.executable, "-c", script], env=dict(os.environ, QT_QPA_PLATFORM="cocoa"))
    try:
        assert _until(cocoa, lambda: macnative.full_screen_over(view), 12)
    finally:
        other.terminate()
        other.wait(10)
    assert _until(cocoa, lambda: not macnative.full_screen_over(view), 12)
    stage.close()


def test_the_login_item_says_how_it_stands(cocoa):
    """Only asked, never changed, here: run from source, the main bundle is Python's, not Chatmon.app."""
    from chatmon import macnative

    assert macnative.login_item() in (macnative.NOT_REGISTERED, macnative.ENABLED, macnative.REQUIRES_APPROVAL, macnative.NOT_FOUND)


def _objc():
    """What the tests below ask of a native menu, with each call's exact prototype."""
    import ctypes

    from chatmon import macnative

    rt = macnative._rt()
    send = ctypes.cast(rt.lib.objc_msgSend, ctypes.c_void_p).value
    at = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(send)  # itemAtIndex:
    run = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(send)  # performActionForItemAtIndex:
    yes = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(send)

    def items(menu):
        return [at(menu, rt.sel("itemAtIndex:"), i) for i in range(rt.long(menu, rt.sel("numberOfItems")))]

    def text(obj, name):
        return rt.text(rt.obj(obj, rt.sel(name)), rt.sel("UTF8String")).decode()

    return rt, items, text, lambda menu, i: run(menu, rt.sel("performActionForItemAtIndex:"), i), lambda o, name: yes(o, rt.sel(name))


def test_cmd_v_comes_through_an_edit_menu_of_chatmons_own(cocoa):
    """macOS counts a paste as yours only from a native menu item (its pasteboard privacy): Cmd+V is that one's."""
    from chatmon import macnative

    rt, items, text, perform, _ = _objc()
    pasted = []
    assert macnative.edit_menu(lambda: pasted.append(True))
    assert macnative.edit_menu(lambda: pasted.append(True))  # once only
    app = rt.obj(rt.cls("NSApplication"), rt.sel("sharedApplication"))
    edits = [i for i in items(rt.obj(app, rt.sel("mainMenu"))) if text(i, "title") == "Edit" and rt.obj(i, rt.sel("submenu"))]
    assert len(edits) == 1
    edit = rt.obj(edits[0], rt.sel("submenu"))
    (paste,) = items(edit)
    assert text(paste, "title") == "Paste" and text(paste, "keyEquivalent") == "v"
    perform(edit, 0)
    assert pasted == [True]


def test_a_menu_shown_natively_has_the_qmenus_items_and_triggers_its_actions(cocoa):
    from PyQt6.QtWidgets import QMenu

    from chatmon import macnative

    rt, items, text, perform, yes = _objc()
    chosen = []
    menu = QMenu()
    menu.addAction("Attach files…", lambda: chosen.append("attach"))
    menu.addAction("&Paste from the clipboard", lambda: chosen.append("paste"))
    menu.addAction("Nothing to take off").setEnabled(False)
    menu.addSection("Your chats")
    keep = menu.addAction("Keep chat history")
    keep.setCheckable(True)
    keep.setChecked(True)
    menu.addMenu("A chat").addAction("Carry on", lambda: chosen.append("carry on"))
    macnative._menus().actions = []
    native = macnative._menus().mirror(menu)
    listed = items(native)
    assert [text(i, "title") for i in listed] == ["Attach files…", "Paste from the clipboard", "Nothing to take off", "", "Your chats", "Keep chat history", "A chat"]
    assert [yes(i, "isEnabled") for i in listed] == [True, True, False, False, False, True, True]
    assert yes(listed[3], "isSeparatorItem") and rt.long(listed[5], rt.sel("state")) == 1
    perform(native, 1)
    perform(native, 5)
    perform(rt.obj(listed[6], rt.sel("submenu")), 0)
    assert chosen == ["paste", "carry on"] and not keep.isChecked()


def test_menu_text_is_as_macos_shows_it():
    from chatmon import macnative

    assert macnative.menu_text("&Paste") == "Paste"
    assert macnative.menu_text("Save && quit") == "Save & quit"
    assert macnative.menu_text("Cu&t\tCtrl+X") == "Cut"
