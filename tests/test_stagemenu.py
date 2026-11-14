"""The penguin's menu as the stage draws it on the Wayland overlay."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPointF, QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QKeyEvent, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMenu  # noqa: E402

from chatmon import stagemenu  # noqa: E402
from chatmon.stagemenu import StageMenu, contrast  # noqa: E402

SCREEN = QRect(0, 0, 1280, 800)
CORNER = QPointF(100, 100)


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def menu(qapp):
    m = QMenu()
    ran = []
    m.addAction("Ask", lambda: ran.append("ask"))
    sub = m.addMenu("Brain")
    sub.addSection("Tools")
    sub.addAction("Claude Code", lambda: ran.append("claude"))
    off = sub.addAction("Grok (not found)")
    off.setEnabled(False)
    sub.addAction("Codex", lambda: ran.append("codex"))
    m.addSeparator()
    walk = m.addAction("Walk around")
    walk.setCheckable(True)
    walk.setChecked(True)
    m.addAction("&Quit", lambda: ran.append("quit"))
    yield m, ran, walk
    m.deleteLater()


def opened(m, clock=None, at=CORNER, area=SCREEN) -> StageMenu:
    sm = StageMenu(clock=clock or Clock())
    sm.open(m, at, area)
    return sm


def centre(sm: StageMenu, panel: int, text: str) -> QPointF:
    p = sm.panels[panel]
    i = next(i for i, item in enumerate(p.items) if item.action.text() == text)
    return QPointF(p.item_rect(i).translated(p.rect.topLeft()).center())


def lit(sm: StageMenu) -> str | None:
    hover = sm.hover
    return None if hover is None else sm.panels[hover[0]].items[hover[1]].action.text()


def press(sm: StageMenu, key, text: str = "") -> bool:
    return sm.key(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text))


def test_it_opens_at_the_pointer_and_stays_on_screen(menu):
    m, _ran, _walk = menu
    sm = opened(m, at=QPointF(1270, 790))  # bottom-right corner: it goes up and left
    (panel,) = sm.panels
    assert SCREEN.contains(panel.rect)
    assert panel.rect.right() <= 1270 and panel.rect.bottom() <= 790


def test_submenus_open_after_the_pointer_rests_and_actions_run_after_it_closes(menu):
    m, ran, _walk = menu
    clock = Clock()
    sm = opened(m, clock)
    sm.move(centre(sm, 0, "Brain"))
    assert len(sm.panels) == 1 and sm.next_change() == pytest.approx(clock.t + stagemenu.SUBMENU_DELAY)
    clock.t += 0.2
    sm.tick()
    assert len(sm.panels) == 1  # not yet
    clock.t += 0.06
    sm.tick()
    assert len(sm.panels) == 2
    assert sm.press(centre(sm, 1, "Grok (not found)")) is None and sm.is_open()  # disabled: nothing
    assert sm.press(centre(sm, 1, "Tools")) is None and sm.is_open()  # a section heading
    action = sm.press(centre(sm, 1, "Claude Code"))
    assert not sm.is_open() and action is not None
    action.trigger()
    assert ran == ["claude"]


def test_a_click_opens_a_submenu_at_once(menu):
    m, _ran, _walk = menu
    sm = opened(m)
    assert sm.press(centre(sm, 0, "Brain")) is None and len(sm.panels) == 2


def test_a_diagonal_move_towards_the_open_submenu_keeps_it(menu):
    m, _ran, _walk = menu
    clock = Clock()
    sm = opened(m, clock)
    sm.press(centre(sm, 0, "Brain"))
    sub = sm.panels[1]
    sm.move(centre(sm, 0, "Walk around"))  # crossing a sibling on the way
    clock.t += 0.1
    sm.tick()
    assert sm.panels[1] is sub
    sm.move(centre(sm, 1, "Codex"))  # in the submenu in time: it stays
    clock.t += 1
    sm.tick()
    assert sm.panels[1] is sub and lit(sm) == "Codex" and sm.panels[0].active == sub.opener
    sm.move(centre(sm, 0, "Walk around"))  # resting on a sibling: the submenu goes
    clock.t += 0.3
    sm.tick()
    assert len(sm.panels) == 1 and lit(sm) == "Walk around"


def test_moving_within_the_same_item_builds_nothing_again(menu):
    m, _ran, _walk = menu
    clock = Clock()
    sm = opened(m, clock)
    sm.press(centre(sm, 0, "Brain"))
    sub = sm.panels[1]
    look = sm.look()
    for dx in range(-20, 21, 5):
        sm.move(centre(sm, 0, "Brain") + QPointF(dx, 0))
        clock.t += 0.3
        sm.tick()
        assert sm.panels[1] is sub and sm.look() == look and sm.next_change() == float("inf")


def test_checkable_items_toggle_and_a_click_elsewhere_closes_it(menu):
    m, _ran, walk = menu
    sm = opened(m)
    sm.press(centre(sm, 0, "Walk around")).trigger()
    assert not walk.isChecked()
    sm.open(m, QPointF(100, 100), SCREEN)
    assert sm.press(QPointF(900, 600)) is None and not sm.is_open()


def test_the_keyboard_moves_opens_picks_and_closes(menu):
    m, ran, _walk = menu
    sm = opened(m)
    assert press(sm, Qt.Key.Key_Down) and lit(sm) == "Ask"
    press(sm, Qt.Key.Key_Down)
    assert lit(sm) == "Brain"
    press(sm, Qt.Key.Key_Down)  # over the separator
    assert lit(sm) == "Walk around"
    press(sm, Qt.Key.Key_End)
    assert lit(sm) == "&Quit"
    press(sm, Qt.Key.Key_Down)  # round to the top
    assert lit(sm) == "Ask"
    press(sm, Qt.Key.Key_Home)
    press(sm, Qt.Key.Key_Up)
    assert lit(sm) == "&Quit"
    press(sm, Qt.Key.Key_B, "b")  # a letter: the next item starting with it
    assert lit(sm) == "Brain" and len(sm.panels) == 1
    press(sm, Qt.Key.Key_Right)  # into the submenu, its first item lit (not the section, not the disabled)
    assert len(sm.panels) == 2 and lit(sm) == "Claude Code"
    press(sm, Qt.Key.Key_Down)
    assert lit(sm) == "Codex"  # the disabled one is skipped
    press(sm, Qt.Key.Key_Left)
    assert len(sm.panels) == 1 and lit(sm) == "Brain"
    press(sm, Qt.Key.Key_Return)  # Enter on a submenu opens it
    assert len(sm.panels) == 2
    press(sm, Qt.Key.Key_Escape)  # Esc: back one menu
    assert len(sm.panels) == 1 and sm.is_open()
    press(sm, Qt.Key.Key_Up)
    press(sm, Qt.Key.Key_Return)
    assert not sm.is_open()
    sm.take_chosen().trigger()
    assert ran == ["ask"]
    sm.open(m, QPointF(100, 100), SCREEN)
    press(sm, Qt.Key.Key_Q, "q")  # its & letter picks it
    assert not sm.is_open() and sm.take_chosen().text() == "&Quit"
    sm.open(m, QPointF(100, 100), SCREEN)
    assert press(sm, Qt.Key.Key_Escape) and not sm.is_open()
    assert not press(sm, Qt.Key.Key_Down)  # closed: not its key


def test_a_menu_taller_than_the_screen_scrolls(qapp):
    m = QMenu()
    for i in range(60):
        m.addAction(f"Chat {i:02d}")
    clock = Clock()
    sm = opened(m, clock, at=QPointF(50, 20), area=QRect(0, 0, 600, 400))
    panel = sm.panels[0]
    assert panel.rect.height() <= 400 - 2 * stagemenu.MARGIN and panel.scrolls()
    shown = lambda: [i for i in range(60) if panel.view().contains(panel.item_rect(i))]  # noqa: E731
    assert 0 in shown() and 59 not in shown()
    sm.wheel(QPointF(panel.rect.center()), -120)  # a notch down
    assert panel.scroll > 0 and 0 not in shown()
    sm.wheel(QPointF(panel.rect.center()), 1200)
    assert panel.scroll == 0
    down = QPointF(panel.rect.center().x(), panel.rect.bottom() - stagemenu.SCROLLER / 2)
    sm.move(down)  # resting on the down arrow: a step at a time
    steps = []
    for _ in range(5):
        sm.tick()
        steps.append(panel.scroll)
        clock.t += stagemenu.SCROLL_REPEAT
    assert steps == sorted(steps) and steps[-1] > steps[0] > 0
    sm.move(QPointF(panel.rect.center()))
    assert sm.next_change() == float("inf")  # off the arrow: it stops
    press(sm, Qt.Key.Key_End)
    assert lit(sm) == "Chat 59" and 59 in shown()
    press(sm, Qt.Key.Key_Home)
    assert 0 in shown() and panel.scroll == 0
    m.deleteLater()


def test_headers_and_shortcuts_read_well_and_the_lit_row_is_solid(qapp):
    from chatmon import bubble

    for fill, text in ((QColor("#ffffff"), QColor("#1a1a1a")), (QColor("#202024"), QColor("#f0f0f0")), (QColor("#fdf6e3"), QColor("#586e75"))):
        quiet = stagemenu.muted(text, fill)
        assert contrast(quiet, fill) >= stagemenu.CONTRAST, (fill.name(), text.name())
        assert contrast(quiet, fill) < contrast(text, fill) or contrast(text, fill) <= stagemenu.MUTED_AIM  # quieter, where it can be
    colours = stagemenu.palette()
    solid_fill = QColor(colours.fill)
    solid_fill.setAlpha(255)
    assert contrast(colours.muted, solid_fill) >= stagemenu.CONTRAST
    assert colours.hover.alpha() == 255 and contrast(colours.hover_text, colours.hover) >= stagemenu.CONTRAST
    assert colours.hover.rgb() == bubble.ACCENT.rgb()


def render(sm: StageMenu, size=(400, 400)) -> QImage:
    img = QImage(*size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    sm.paint(p)
    p.end()
    return img


def test_it_draws_the_lit_row_solid_with_an_outline(menu):
    m, _ran, _walk = menu
    sm = opened(m, at=QPointF(10, 10), area=QRect(0, 0, 400, 400))
    img = render(sm)
    inside = sm.panels[0].rect.center()
    assert img.pixelColor(inside).alpha() > 200 and img.pixelColor(390, 390).alpha() == 0
    press(sm, Qt.Key.Key_End)  # "Quit" lit, from the keyboard
    img = render(sm)
    panel = sm.panels[0]
    row = panel.item_rect(panel.active).translated(panel.rect.topLeft())
    colours = stagemenu.palette()
    fill_at = img.pixelColor(row.right() - stagemenu.ARROW // 2, row.center().y())  # inside the row, away from the label
    assert fill_at.alpha() == 255 and fill_at.rgb() == colours.hover.rgb()  # solid, not a tint
    edge = img.pixelColor(row.left() + 4, row.center().y())  # where the outline runs
    assert contrast(edge, colours.hover) >= 1.5 and edge.rgb() != colours.hover.rgb()


def test_rows_grow_with_the_font(menu):
    m, _ran, _walk = menu
    app = QApplication.instance()
    default = app.font()
    try:
        for points in (default.pointSizeF(), 24.0):
            font = QFont(default)
            font.setPointSizeF(points)
            app.setFont(font)
            sm = opened(m)
            row = next(i.rect.height() for i in sm.panels[0].items if i.kind == "action")
            assert row == max(stagemenu.ROW, QFontMetrics(font).height() + stagemenu.ROW_PAD)
        assert row > stagemenu.ROW  # 24 pt doesn't fit in 26 px
    finally:
        app.setFont(default)
