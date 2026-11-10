"""The penguin's menu as the stage draws it on the Wayland overlay."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRect  # noqa: E402
from PyQt6.QtGui import QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMenu  # noqa: E402

from penguin_companion.stagemenu import StageMenu  # noqa: E402


@pytest.fixture
def menu():
    QApplication.instance() or QApplication([])
    m = QMenu()
    ran = []
    m.addAction("Ask", lambda: ran.append("ask"))
    sub = m.addMenu("Brain")
    sub.addSection("Tools")
    sub.addAction("Claude Code", lambda: ran.append("claude"))
    off = sub.addAction("Grok (not found)")
    off.setEnabled(False)
    m.addSeparator()
    walk = m.addAction("Walk around")
    walk.setCheckable(True)
    walk.setChecked(True)
    yield m, ran, walk
    m.deleteLater()


def centre(sm: StageMenu, panel: int, text: str) -> QPointF:
    p = sm.panels[panel]
    item = next(i for i in p.items if i.action.text() == text)
    return QPointF(item.rect.translated(p.rect.topLeft()).center())


def test_it_opens_at_the_pointer_and_stays_on_screen(menu):
    m, _ran, _walk = menu
    sm = StageMenu()
    sm.open(m, QPointF(1270, 790), QRect(0, 0, 1280, 800))  # bottom-right corner: it goes up and left
    (panel,) = sm.panels
    assert QRect(0, 0, 1280, 800).contains(panel.rect)
    assert panel.rect.right() <= 1270 and panel.rect.bottom() <= 790


def test_submenus_open_on_hover_and_actions_run_after_it_closes(menu):
    m, ran, _walk = menu
    sm = StageMenu()
    sm.open(m, QPointF(100, 100), QRect(0, 0, 1280, 800))
    sm.move(centre(sm, 0, "Brain"))
    assert len(sm.panels) == 2
    assert sm.press(centre(sm, 1, "Grok (not found)")) is None and sm.is_open()  # disabled: nothing
    assert sm.press(centre(sm, 1, "Tools")) is None and sm.is_open()  # a section heading
    action = sm.press(centre(sm, 1, "Claude Code"))
    assert not sm.is_open() and action is not None
    action.trigger()
    assert ran == ["claude"]


def test_checkable_items_toggle_and_a_click_elsewhere_closes_it(menu):
    m, _ran, walk = menu
    sm = StageMenu()
    sm.open(m, QPointF(100, 100), QRect(0, 0, 1280, 800))
    sm.press(centre(sm, 0, "Walk around")).trigger()
    assert not walk.isChecked()
    sm.open(m, QPointF(100, 100), QRect(0, 0, 1280, 800))
    assert sm.press(QPointF(900, 600)) is None and not sm.is_open()


def test_it_draws(menu):
    m, _ran, _walk = menu
    sm = StageMenu()
    sm.open(m, QPointF(10, 10), QRect(0, 0, 400, 400))
    img = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    sm.paint(p)
    p.end()
    inside = sm.panels[0].rect.center()
    assert img.pixelColor(inside).alpha() > 200 and img.pixelColor(390, 390).alpha() == 0
