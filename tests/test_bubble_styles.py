"""The painted chat bubbles: their art loads, text fits inside them, the notch follows the penguin, and
their animation is a loop that closes by construction."""

import json
import re
from pathlib import Path

import pytest
from PyQt6.QtCore import QPoint, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from chatmon import bubbleart, paths, styles
from chatmon.bubble import AskBox, SpeechBubble

PAINTED = ["electric", "fire", "ghost", "fairy", "leaf"]
SIZES = [(300, 92), (220, 60), (377, 141)]  # text areas, display px


def render(art, text: QSizeF, age: float, animate: bool = True, tip: float | None = None) -> bytes:
    frame = art.frame_for(text)
    img = QImage(round(frame.size.width()), round(frame.size.height()), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    lo, hi = art.tail_range(text.width())
    art.paint(p, 0, 0, text, (lo + hi) / 2 if tip is None else tip, age, animate)
    p.end()
    return img.constBits().asstring(img.sizeInBytes())


def test_every_painted_style_has_its_art(qapp):
    folder = paths.bubbles_dir()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name in PAINTED:
        art = bubbleart.art(name)
        assert art is not None, name
        assert not art.still.isNull() and art.layers, name
        for fx in manifest[name]["fx"]:
            assert fx["type"] in bubbleart.LAYERS, (name, fx["type"])
            if "file" in fx:
                assert (folder / fx["file"]).is_file(), (name, fx["file"])
    assert any(isinstance(layer, bubbleart.Crawler) for layer in bubbleart.art("leaf").layers), "the leaf bubble's caterpillar"
    assert bubbleart.art("plain") is None


def test_no_frame_sheet_animation_is_left(qapp):
    """Looping motion is never a generated sheet of whole-bubble frames (see art/bubbles/README.md)."""
    folder = paths.bubbles_dir()
    assert not list(folder.glob("*-anim.png"))
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name in PAINTED:
        assert "frames" not in manifest[name] and "fps" not in manifest[name], name


def test_the_app_draws_bubbles_with_qt_alone():
    """The art tools may use numpy and Pillow; the app itself must not."""
    package = Path(bubbleart.__file__).parent
    for source in package.glob("*.py"):
        found = re.findall(r"^\s*(?:import|from)\s+(numpy|PIL|cv2|scipy)\b", source.read_text(encoding="utf-8"), re.M)
        assert not found, (source.name, found)


def test_cut_lines_fall_on_whole_display_pixels(qapp):
    """The art is twice display size, so every distance the 9-slice cuts at must be an even number of art
    pixels, or two pieces meet on a half pixel and a bright line shows at the join."""
    for name in PAINTED:
        art = bubbleart.art(name)
        assert art.k == 0.5, name
        x0, y0, x1, y1 = art.text
        n0, n1 = art.notch
        cuts = {"left": x0, "top": y0, "right": art.w - x1, "bottom": art.h - y1, "corner": art.corner, "notch": n1 - n0, "tip": art.tip[0] - n0}
        for what, value in cuts.items():
            assert value % 2 == 0, (name, what, value)
        for margin in art.margins():
            assert margin == round(margin), name


def test_text_sits_inside_the_painted_bubble(qapp):
    for name in PAINTED:
        b = SpeechBubble()
        b.set_style(styles.get(name), True)
        b.show("Sparky", "Your build finished. All 98 tests passed.", [("Open", None), ("Later", None)], None, 0.0)
        art = b.art
        k, (x0, y0, x1, y1) = art.k, art.text
        fill_right = b.size.width() - (art.w - x1) * k
        fill_bottom = b.size.height() - (art.h - y1) * k
        for r in [b._content] + [btn.rect for btn in b.buttons]:
            assert r.left() >= x0 * k and r.top() >= y0 * k, name
            assert r.right() <= fill_right and r.bottom() <= fill_bottom, name
        assert b.hit(b.buttons[0].rect.center()) == 0
        assert b.hit(b._close_rect.center()) == "close"


def test_the_notch_follows_the_penguin_but_stays_on_the_bubble(qapp):
    art = bubbleart.art("electric")
    lo, hi = art.tail_range(300)
    assert lo < hi
    frame = art.frame_for(QSizeF(300, 90))
    img = QImage(round(frame.size.width()), round(frame.size.height()), QImage.Format.Format_ARGB32_Premultiplied)

    def tip_x(asked: float) -> float:
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        art.paint(p, 0, 0, QSizeF(300, 90), asked, 0.0, False)
        p.end()
        y = round(frame.tail[1]) - 3  # just above the tip: only the notch is there
        xs = [x for x in range(img.width()) if img.pixelColor(x, y).alpha() > 200]
        return sum(xs) / len(xs)

    for asked in (lo, (lo + hi) / 2, hi):
        assert abs(tip_x(asked) - asked) < 6
    assert abs(tip_x(-500) - lo) < 6  # pointing past the end: it stops at the end
    assert abs(tip_x(5000) - hi) < 6


def test_an_animated_bubble_asks_to_be_redrawn_and_a_still_one_does_not(qapp):
    b = SpeechBubble()
    b.set_style(styles.get("fire"), True)
    b.show("Sparky", "hi", None, None, 0.0)
    assert b.anim_key(0.0) != b.anim_key(0.1)
    b.set_style(styles.get("fire"), False)
    assert b.anim_key(0.1) == -1
    b.set_style(styles.get("plain"), True)
    assert b.anim_key(0.1) == -1


def test_the_border_line_is_one_closed_walk(qapp):
    for name in PAINTED:
        art = bubbleart.art(name)
        lo, _ = art.tail_range(300)
        rim = art.rim(300, 92, lo)
        assert rim.length == pytest.approx(sum(part[1] for part in rim.parts))
        ax, ay, _ = rim.at(0.0)
        bx, by, _ = rim.at(rim.length)
        assert (ax, ay) == pytest.approx((bx, by), abs=1e-6), name
        step = rim.length / 400
        last = rim.at(0.0)
        for i in range(1, 401):  # no jump anywhere along it
            here = rim.at(i * step)
            assert abs(here[0] - last[0]) + abs(here[1] - last[1]) <= 2 * step + 1e-6, (name, i)
            last = here
        for f in (0.0, 0.2, 0.5, 0.77, 0.999):  # sprites keep off the corners and the notch
            x, y, _ = rim.at(rim.on_straight(f))
            on_bottom = abs(y - rim.y1) < 1e-6
            assert not (on_bottom and rim.notch[0] - 8 < x < rim.notch[1] + 8), (name, f)


def test_drifting_strips_have_no_seam_in_space_or_time(qapp):
    """Whole tiles round the border (no seam in space). In time a strip is two copies whose weights add
    up to 1, and a copy is at weight 0 at the moment it steps back (no seam in time), so it can drift
    slowly instead of having to cover a whole tile per cycle."""
    seen = 0
    for name in PAINTED:
        art = bubbleart.art(name)
        for w, h in SIZES:
            lo, hi = art.tail_range(w)
            rim = art.rim(w, h, round((lo + hi) / 2))
            for layer in art.layers:
                if not isinstance(layer, bubbleart.Scroll):
                    continue
                seen += 1
                _, tile = layer.fitted(rim)
                tiles = rim.length / tile
                assert abs(tiles - round(tiles)) < 1e-9 and round(tiles) >= 1, (name, w, h)
                assert abs(tile / layer.tile - 1) < 0.34, "the strip is stretched too far to fit"
                assert abs(layer.speed) <= 20, f"{name}: {layer.speed} px a second is not calm"
                assert abs(layer.speed) * layer.period < tile, "a copy must not lap its own tile while shown"
                period, n = layer.period, 240
                before = layer.copies(-1e-9 % period, tile)
                for i in range(n + 1):
                    now = layer.copies(period * i / n, tile)
                    assert sum(weight for weight, _ in now) == pytest.approx(1.0)
                    for (w0, s0), (w1, s1) in zip(before, now, strict=True):
                        moved = (s1 - s0 + tile / 2) % tile - tile / 2  # the shortest way round the tile
                        if abs(moved) > abs(layer.speed) * period / n + 1e-6:  # it stepped back
                            assert w0 < 1e-3 and w1 < 1e-3, (name, i)  # one sample either side of the step
                    before = now
                for one, other in zip(layer.copies(0.4, tile), layer.copies(0.4 + period, tile), strict=True):
                    assert one == pytest.approx(other)
    assert seen >= 9  # ghost has two strips and electric one, at three sizes


def test_a_slow_drift_moves_by_parts_of_a_pixel(qapp):
    """A strip drifting a third of a pixel per redraw must not move in whole-pixel hops (which is what
    QPainter.drawTiledPixmap does): four quarter-pixel steps must each change the picture, about evenly."""
    for name in ("ghost", "electric"):
        art = bubbleart.art(name)
        lo, _ = art.tail_range(300)
        rim = art.rim(300, 92, round(lo))
        layer = next(layer for layer in art.layers if isinstance(layer, bubbleart.Scroll))
        shots = []
        for i in range(5):
            image = layer.band(rim, [(1.0, 3 + i / 4)], 1.0).toImage()
            shots.append(image.constBits().asstring(image.sizeInBytes()))
        steps = [sum(abs(a - b) for a, b in zip(shots[i], shots[i + 1], strict=True)) for i in range(4)]
        assert min(steps) > 0, (name, steps)
        assert max(steps) < 2.5 * min(steps), (name, steps)


def test_every_layer_finishes_whole_cycles_in_one_loop(qapp):
    for name in PAINTED:
        art = bubbleart.art(name)
        for w, h in SIZES:
            text = QSizeF(w, h)
            period = art.loop_period(text)
            lo, _ = art.tail_range(w)
            rim = art.rim(w, h, round(lo))
            for layer in art.layers:
                cycles = period / layer.cycle(rim)
                assert abs(cycles - round(cycles)) < 1e-6 and round(cycles) >= 1, (name, type(layer).__name__)
            if name == "leaf":  # the caterpillar's walk and rest, in whole strides
                crawler = art.layers[0]
                strides = period / crawler.stride
                assert abs(strides - round(strides)) < 1e-6
                assert 8 <= crawler.speed <= 12 and period <= 60
            else:
                assert 3.0 <= period <= 8.0, (name, period)


def test_the_loop_comes_back_to_the_same_picture(qapp):
    """t and t + one period draw the same frame, to the byte; half a period apart they differ."""
    for name in PAINTED:
        art = bubbleart.art(name)
        for w, h in SIZES[:2]:
            text = QSizeF(w, h)
            period = art.loop_period(text)
            for t in (0.0, 0.37, period * 0.61):
                assert render(art, text, t) == render(art, text, t + period), (name, w, t)
                assert render(art, text, t) == render(art, text, t + 3 * period), (name, w, t)
            assert render(art, text, 0.37) != render(art, text, 0.37 + period / 2), name


def test_animation_off_draws_only_the_still(qapp):
    for name in PAINTED:
        art = bubbleart.art(name)
        text = QSizeF(300, 92)
        still = render(art, text, 0.0, animate=False)
        assert still == render(art, text, 2.9, animate=False), name
        assert still != render(art, text, 2.9, animate=True), name


def test_effects_never_touch_the_text_area(qapp):
    for name in PAINTED:
        art = bubbleart.art(name)
        text = QSizeF(300, 92)
        frame = art.frame_for(text)
        w, h = round(frame.size.width()), round(frame.size.height())
        period = art.loop_period(text)
        still = render(art, text, 0.0, animate=False)
        x0, y0, x1, y1 = round(frame.text.left()), round(frame.text.top()), round(frame.text.right()), round(frame.text.bottom())
        for i in range(8):
            moving = render(art, text, period * i / 8 + 0.21)
            assert len(moving) == w * h * 4
            for y in range(y0, y1, 3):
                a, b = (y * w + x0) * 4, (y * w + x1) * 4
                assert moving[a:b] == still[a:b], (name, i, y)


def test_ask_box_wears_the_style_and_keeps_its_input_inside_the_bubble(qapp):
    box = AskBox()
    try:
        for name in PAINTED + ["plain"]:
            box.set_style(styles.get(name), True)
            box.open(QPoint(600, 600), "Ask Sparky", "Enter to ask", "Ask anything", activate=False)
            body, tail = box.input_rects()
            assert box.rect().contains(body) and body.width() > 200, name
            entry = box.entry.geometry()
            assert body.contains(entry.topLeft()) and body.contains(entry.bottomRight()), name
            assert tail.top() <= body.bottom() + 1
            box.dismiss()
    finally:
        box.deleteLater()


def test_unknown_style_falls_back_to_electric(qapp):
    assert styles.get("nope").name == "electric"
    assert styles.get(None).name == "electric"


def test_electric_lightning_runs_round_the_border(qapp):
    """The pulses go right round the border, evenly spaced, at a steady speed, and are back where they
    began after one period, whatever the bubble's size."""
    art = bubbleart.art("electric")
    runner = next(layer for layer in art.layers if isinstance(layer, bubbleart.Runner))
    wake = next(layer for layer in art.layers if isinstance(layer, bubbleart.Wake))
    assert (wake.period, wake.count, wake.laps) == (runner.period, runner.count, runner.laps)
    for w, h in SIZES:
        lo, hi = art.tail_range(w)
        rim = art.rim(w, h, round((lo + hi) / 2))
        period, count = runner.period, runner.count

        def heads(t: float, rim=rim, period=period, count=count) -> list[float]:
            return bubbleart._heads(rim, t, period, count, runner.laps)

        assert heads(0.3) == pytest.approx(heads(0.3 + period))
        gaps = sorted(heads(1.1))
        for a, b in zip(gaps, gaps[1:], strict=False):
            assert b - a == pytest.approx(rim.length / count)
        step = abs(runner.laps) * rim.length / period * 0.1  # px in a tenth of a second
        for t in (0.0, 1.3, 5.9):
            for a, b in zip(heads(t), heads(t + 0.1), strict=True):
                assert (b - a) % rim.length == pytest.approx(step)
        seen = set()  # a head visits every part of the border in one period
        for i in range(400):
            seen.add(int(heads(period * i / 400)[0] / rim.length * 20))
        assert seen == set(range(20))


def test_a_pulse_is_a_bright_head_with_a_fading_tail(qapp):
    art = bubbleart.art("electric")
    runner = next(layer for layer in art.layers if isinstance(layer, bubbleart.Runner))
    lo, _ = art.tail_range(300)
    rim = art.rim(300, 92, round(lo))
    t = runner.period * 0.31
    tail = max(8.0, min(runner.tail, rim.length / runner.count - runner.lead - 2))
    pulses = runner.pulses(rim, t)
    band = QPixmap(round(rim.length + 2 * runner.MARGIN), 8)  # as `paint` has it: solid where lit, clear elsewhere
    band.fill(Qt.GlobalColor.transparent)
    q = QPainter(band)
    for _, _, start in pulses:
        q.fillRect(QRectF(start, 0, tail + runner.lead, 8), QColor("white"))
    q.end()
    runner.envelope(band, pulses, tail, 1.0)
    image = band.toImage()
    way = 1 if runner.laps > 0 else -1
    head = bubbleart._heads(rim, t, runner.period, runner.count, runner.laps)[0]

    def level(offset: float) -> int:  # the envelope `offset` px ahead of the head (negative: behind it)
        return image.pixelColor(round(runner.MARGIN + (head + way * offset) % rim.length), 4).alpha()

    assert level(0) > 200
    assert level(runner.lead + 4) == 0  # dark ahead of it
    behind = [level(-d) for d in (0, 20, 50, 90, 140)]
    assert behind == sorted(behind, reverse=True) and behind[-1] < 80, behind


def test_arcs_strike_only_where_a_head_has_just_passed(qapp):
    art = bubbleart.art("electric")
    wake = next(layer for layer in art.layers if isinstance(layer, bubbleart.Wake))
    reach = wake.size.width() * wake.scale / 2
    for w, h in SIZES:
        lo, hi = art.tail_range(w)
        rim = art.rim(w, h, round((lo + hi) / 2))
        places = wake.places(rim)
        assert places, (w, h)
        for s in places:  # a straight arc has straight border under it, and never sits on the notch
            x, y, ang = rim.at(s)
            assert rim.at(s - reach)[2] == ang == rim.at(s + reach)[2], (w, h, s)
            assert not (abs(y - rim.y1) < 1e-6 and rim.notch[0] - 8 < x < rim.notch[1] + 8), (w, h, s)
        speed = abs(wake.laps) * rim.length / wake.period
        assert wake.life * speed < rim.length / wake.count  # an arc is gone before the next head arrives


def test_the_electric_border_is_cyan_and_its_lightning_yellow(qapp):
    """The painted border keeps its colour; only what runs along it is yellow."""
    folder = paths.bubbles_dir()

    def mean_colour(name: str, least: int) -> tuple[float, float, float]:
        image = QImage(str(folder / name)).convertToFormat(QImage.Format.Format_RGBA8888)
        total, n = [0, 0, 0], 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                c = image.pixelColor(x, y)
                if c.alpha() > 200 and max(c.red(), c.green(), c.blue()) >= least:
                    total = [total[0] + c.red(), total[1] + c.green(), total[2] + c.blue()]
                    n += 1
        assert n > 20, name
        return total[0] / n, total[1] / n, total[2] / n

    r, g, b = mean_colour("electric-still.png", 200)  # the bright part of the still: its neon edge
    assert b > r + 60 and g > r + 60, (r, g, b)
    for name in ("electric-arcs.png", "electric-current.png"):
        r, g, b = mean_colour(name, 120)
        assert r > b + 40 and g > b + 20, (name, r, g, b)



def test_an_answer_can_never_make_qt_read_a_file(qapp, tmp_path):
    """An image in markdown would have Qt read the file it names: /dev/zero, a pipe, anything."""
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not for showing")
    text = f"Look: ![x]({secret}) and ![y][r] done\n\n[r]: file://{secret}"

    def images(doc) -> int:
        n, block = 0, doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                n += it.fragment().charFormat().isImageFormat()
                it += 1
            block = block.next()
        return n

    message = SpeechBubble()
    message.show("Hi", text, [], None, 0.0)
    assert images(message.doc) == 0 and message.doc.toPlainText().count("[image]") == 2
    box = AskBox()
    box.set_answer(text)
    assert images(box.answer.document()) == 0 and "[image]" in box.answer.toPlainText()
