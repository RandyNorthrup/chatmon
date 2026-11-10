"""Make the README's pictures and animations, drawn by Chatmon's own code.

Usage: python art/tools/readme_media.py [what ...]   (what: portraits, banner, social, hero, agents, styles, ask; all if none)

Everything is drawn the way the app draws it: the same sprites, behaviour and bubbles (chatmon.sprites,
chatmon.behavior, chatmon.bubble), at twice the size for sharp screens, on a card of its own. Animations
are frames encoded by ffmpeg as animated WebP. Fonts: art/fonts (SIL Open Font License). Writes to
docs/media.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])

from chatmon import companions, styles  # noqa: E402
from chatmon.behavior import Behavior  # noqa: E402
from chatmon.bubble import AskBox, SpeechBubble  # noqa: E402
from chatmon.sprites import Sprites  # noqa: E402

OUT = ROOT / "docs" / "media"
DPR = 2  # device pixels per pixel: the pictures are made at twice their size
FPS = 15
ORDER = ["penguin", "fire-red-panda", "ghost-rabbit", "fairy-axolotl", "leaf-pangolin"]
GLOW = {  # each chatmon's colour, for the light behind it
    "penguin": "#45d3f7",
    "fire-red-panda": "#ff8a2a",
    "ghost-rabbit": "#b9a6f5",
    "fairy-axolotl": "#f6a2bf",
    "leaf-pangolin": "#7bd35a",
}


def _font(file: str) -> str:
    families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(ROOT / "art" / "fonts" / file)))
    if not families:
        raise SystemExit(f"couldn't load art/fonts/{file}")
    return families[0]


TITLE = _font("LilitaOne-Regular.ttf")
BODY = _font("Nunito[wght].ttf")


def font(family: str, px: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(family)
    f.setPixelSize(round(px))
    f.setWeight(weight)
    f.setVariableAxis(QFont.Tag("wght"), float(weight.value))  # Nunito is a variable font: say the weight outright
    return f


def canvas(w: int, h: int) -> QImage:
    img = QImage(w * DPR, h * DPR, QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(DPR)
    img.fill(Qt.GlobalColor.transparent)
    return img


def card(p: QPainter, w: float, h: float, glows: list[tuple[float, float, str, float]], radius: float = 22, floor: float | None = None) -> None:
    """A night-sky card with rounded corners, soft lights in it, and a taskbar for chatmons to stand on."""
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.save()
    p.setClipPath(shape)
    sky = QLinearGradient(0, 0, w * 0.35, h)
    sky.setColorAt(0, QColor("#141c3d"))
    sky.setColorAt(0.6, QColor("#0d1229"))
    sky.setColorAt(1, QColor("#1a0f2e"))
    p.fillRect(QRectF(0, 0, w, h), sky)
    rng = random.Random(7)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(int(w * h / 2600)):  # a few faint stars
        c = QColor(255, 255, 255, rng.randint(25, 90))
        p.setBrush(c)
        r = rng.choice((0.6, 0.8, 1.0, 1.3))
        p.drawEllipse(QPointF(rng.uniform(0, w), rng.uniform(0, h * 0.8)), r, r)
    for x, y, colour, reach in glows:
        g = QRadialGradient(QPointF(x, y), reach)
        c = QColor(colour)
        c.setAlpha(80)
        g.setColorAt(0, c)
        c.setAlpha(0)
        g.setColorAt(1, c)
        p.fillRect(QRectF(0, 0, w, h), g)
    if floor is not None:  # the taskbar
        bar = QLinearGradient(0, floor, 0, h)
        bar.setColorAt(0, QColor(255, 255, 255, 34))
        bar.setColorAt(0.04, QColor(255, 255, 255, 14))
        bar.setColorAt(1, QColor(255, 255, 255, 8))
        p.fillRect(QRectF(0, floor, w, h - floor), bar)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawLine(QPointF(0, floor + 0.5), QPointF(w, floor + 0.5))
    p.restore()
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)


class Actor:
    """One chatmon on a card: its sprites, its behaviour and its bubble, as the app has them."""

    def __init__(self, cid: str, x: float, floor: float, size: int = 120, seed: int = 1, width: float = 0):
        companion = companions.COMPANIONS[cid]
        self.cid = cid
        self.sprites = Sprites(companion.anim_dir(), size, DPR)
        self.behavior = Behavior(self.sprites.anims(), now=0.0, x=x, rng=random.Random(seed), walk=False)
        self.floor, self.width = floor, width
        self.bubble = SpeechBubble()
        self.bubble.set_style(styles.get(companion.bubble_style), True)
        self.cues: list[tuple[float, object]] = []  # (when, what to do to the behaviour then), as the app would

    def at(self, when: float, do) -> None:
        self.cues.append((when, do))
        self.cues.sort(key=lambda cue: cue[0])

    def say(self, title: str, text: str, at: float, last: float | None = None, buttons=()) -> None:
        self.bubble.show(title, text, [(b, lambda: None) for b in buttons], last, at)

    def paint(self, p: QPainter, t: float) -> None:
        while self.cues and self.cues[0][0] <= t:
            when, do = self.cues.pop(0)
            do(self.behavior, when)
        f = self.behavior.tick(t)
        sprite = self.sprites.frame(f.anim, f.index, f.mirror)
        top = self.floor - sprite.height() - round(f.lift)
        p.drawPixmap(QPointF(round(f.x) - sprite.anchor, top), sprite.pixmap)
        self.bubble.tick(t)
        if self.bubble.drawn():
            head = QPointF(round(f.x), top + 4)
            size = self.bubble.size
            x = min(max(head.x() - size.width() / 2, 6), self.width - size.width() - 6)
            y = max(head.y() - size.height(), 6)
            x, y = round(x * DPR) / DPR, int(y * DPR) / DPR
            p.save()
            p.translate(x, y)
            self.bubble.paint(p, head.x() - x, t)
            p.restore()


def encode(frames_dir: Path, out: Path, width_px: int) -> None:
    """Frames to a looping animated WebP, `width_px` wide."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "%04d.png"),
         "-vf", f"scale={width_px}:-1:flags=lanczos", "-c:v", "libwebp_anim", "-pix_fmt", "yuva420p",
         "-quality", "82", "-compression_level", "6", "-loop", "0", str(out)],
        check=True,
    )


def animate(name: str, w: int, h: int, seconds: float, draw, width_px: int) -> None:
    folder = Path(tempfile.mkdtemp(prefix="chatmon-media-"))
    try:
        for i in range(round(seconds * FPS)):
            img = canvas(w, h)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            draw(p, i / FPS)
            p.end()
            img.save(str(folder / f"{i:04d}.png"))
        encode(folder, OUT / f"{name}.webp", width_px)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(f"{name}.webp: {(OUT / f'{name}.webp').stat().st_size // 1024} KB")


def save(img: QImage, name: str) -> None:
    img.save(str(OUT / name))
    print(f"{name}: {(OUT / name).stat().st_size // 1024} KB")


# -- the pictures


def lineup(p: QPainter, x0: float, gap: float, floor: float, size: int, frames: dict[str, tuple[str, int]] | None = None) -> None:
    """The five standing on a floor, each in a pose (still pictures)."""
    for i, cid in enumerate(ORDER):
        sprites = Sprites(companions.COMPANIONS[cid].anim_dir(), size, DPR)
        anim, index = (frames or {}).get(cid, ("idle", 0))
        sprite = sprites.frame(anim, index, False)
        x = x0 + i * gap
        p.drawPixmap(QPointF(round(x) - sprite.anchor, floor - sprite.height()), sprite.pixmap)


POSES = {"penguin": ("wave", 2), "fire-red-panda": ("idle", 0), "ghost-rabbit": ("idle", 0), "fairy-axolotl": ("wave", 3), "leaf-pangolin": ("idle", 0)}


def banner() -> None:
    w, h, floor = 1280, 400, 352
    img = canvas(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    x0, gap = 752, 118
    card(p, w, h, [(x0 + i * gap, floor - 60, GLOW[c], 150) for i, c in enumerate(ORDER)] + [(160, 120, "#45d3f7", 260)], radius=28, floor=floor)
    title_and_tagline(p, 72, 150, 128, 560)
    lineup(p, x0, gap, floor, 138, POSES)
    p.end()
    save(img, "banner.png")


def title_and_tagline(p: QPainter, x: float, baseline: float, px: float, column: float) -> None:
    """The name, what it is, and what it runs with, in a column `column` px wide."""
    title = QPainterPath()
    title.addText(QPointF(x, baseline), font(TITLE, px), "Chatmon")
    box = title.boundingRect()
    glow = QColor("#45d3f7")
    for spread, alpha in ((14, 18), (8, 30), (4, 46)):  # a soft glow round the letters
        glow.setAlpha(alpha)
        p.strokePath(title, QPen(glow, spread, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    fill = QLinearGradient(box.left(), box.top(), box.right(), box.bottom())
    fill.setColorAt(0, QColor("#e9fbff"))
    fill.setColorAt(0.55, QColor("#8fe6ff"))
    fill.setColorAt(1, QColor("#f6a2bf"))
    p.fillPath(title, fill)
    p.setPen(QColor("#d4dcff"))
    p.setFont(font(BODY, px * 0.2, QFont.Weight.DemiBold))
    p.drawText(QRectF(x + 4, baseline + px * 0.22, column, px * 0.6), Qt.TextFlag.TextWordWrap,
               "Little desktop companions that answer with any AI and keep an eye on your coding agents.")
    p.setFont(font(BODY, px * 0.14, QFont.Weight.Bold))
    chips = ["Linux", "Windows", "macOS", "Claude Code", "Codex", "Gemini", "Cursor"]
    cx, cy = x + 4, baseline + px * 0.98
    for chip in chips:
        tw = p.fontMetrics().horizontalAdvance(chip) + 22
        if cx + tw > x + 4 + column:  # only what fits the column
            break
        rect = QRectF(cx, cy, tw, px * 0.26)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        p.setPen(QColor("#bcd0ff"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, chip)
        cx += tw + 8


def social() -> None:
    """GitHub's link preview: 1280x640 (Settings, Social preview)."""
    w, h, floor = 1280, 640, 560
    img = canvas(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    gap = 200
    x0 = (w - 4 * gap) / 2
    card(p, w, h, [(x0 + i * gap, floor - 80, GLOW[c], 190) for i, c in enumerate(ORDER)], radius=0, floor=floor)
    title = QPainterPath()
    f = font(TITLE, 150)
    title.addText(QPointF(0, 0), f, "Chatmon")
    box = title.boundingRect()
    title.translate((w - box.width()) / 2 - box.left(), 170)
    glow = QColor("#45d3f7")
    for spread, alpha in ((16, 18), (9, 30), (4, 46)):
        glow.setAlpha(alpha)
        p.strokePath(title, QPen(glow, spread, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    fill = QLinearGradient(title.boundingRect().topLeft(), title.boundingRect().bottomRight())
    fill.setColorAt(0, QColor("#e9fbff"))
    fill.setColorAt(0.55, QColor("#8fe6ff"))
    fill.setColorAt(1, QColor("#f6a2bf"))
    p.fillPath(title, fill)
    p.setPen(QColor("#d4dcff"))
    p.setFont(font(BODY, 32, QFont.Weight.DemiBold))
    p.drawText(QRectF(0, 200, w, 60), Qt.AlignmentFlag.AlignHCenter, "Desktop companions that answer with any AI and watch your coding agents")
    lineup(p, x0, gap, floor, 190, POSES)
    p.end()
    save(img, "social-preview.png")


HERO_LINES = [
    ("penguin", "Claude Code finished", "All 227 tests pass."),
    ("fire-red-panda", "Break time", "An hour at the screen. Stretch?"),
    ("ghost-rabbit", "Reminder", "Call Sam at 3 pm."),
    ("fairy-axolotl", "Codex needs you", "Approve the migration?"),
    ("leaf-pangolin", "Heads-up", "Battery at 15%. Plug in soon."),
]


def hero() -> None:
    w, h, floor, gap = 1000, 330, 300, 190
    x0 = (w - 4 * gap) / 2
    actors = {cid: Actor(cid, x0 + i * gap, floor, 112, seed=i + 3, width=w) for i, cid in enumerate(ORDER)}
    turn = 2.8
    for i, (cid, title, text) in enumerate(HERO_LINES):
        actors[cid].say(title, text, at=i * turn - 0.2, last=turn - 0.15)
        actors[cid].at(i * turn, lambda b, now: b.react("wave", now))
    glows = [(x0 + i * gap, floor - 50, GLOW[c], 120) for i, c in enumerate(ORDER)]

    def draw(p: QPainter, t: float) -> None:
        card(p, w, h, glows, floor=floor)
        for actor in actors.values():
            actor.paint(p, t)

    animate("hero", w, h, turn * len(HERO_LINES), draw, 1600)


def agents_demo() -> None:
    """Three tiles: an agent working, needing you, finished."""
    w, h, floor = 330, 290, 262
    scenes = [
        ("agent-working", "ghost-rabbit", "Claude Code is working", "Refactoring the parser…", lambda b, t: b.set_thinking(True, t), ()),
        ("agent-needs-you", "fire-red-panda", "Codex needs you", "Run the database migration?", lambda b, t: b.set_alert(True, t), ("Yes", "Later")),
        ("agent-done", "leaf-pangolin", "Gemini finished", "Deployed to staging.", lambda b, t: b.react("hop", t, times=2), ()),
    ]
    for name, cid, title, text, start, buttons in scenes:
        actor = Actor(cid, w / 2, floor, 112, seed=5, width=w)
        start(actor.behavior, 0.0)
        actor.say(title, text, at=-1.0, buttons=buttons)

        def draw(p: QPainter, t: float, actor=actor, cid=cid) -> None:
            card(p, w, h, [(w / 2, floor - 40, GLOW[cid], 130)], floor=floor)
            actor.paint(p, t)

        animate(name, w, h, 3.2, draw, 495)


def styles_sheet() -> None:
    """The six bubble styles, as messages."""
    cols, cell_w, cell_h = 3, 330, 128
    w, h = cols * cell_w + 40, 2 * cell_h + 40
    img = canvas(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    card(p, w, h, [(w * 0.2, h * 0.3, "#45d3f7", 220), (w * 0.8, h * 0.7, "#f6a2bf", 220)])
    lines = {
        "electric": "Crackling cyan, lightning running round.",
        "fire": "Embers, and low flames along the top.",
        "ghost": "Frosted glass in a violet mist.",
        "fairy": "Blush opal with glints and sparkles.",
        "leaf": "Ivy, and a caterpillar on its way.",
        "plain": "Your desktop's own colours.",
    }
    for i, (name, line) in enumerate(lines.items()):
        b = SpeechBubble()
        b.set_style(styles.get(name), True)
        b.show(styles.get(name).label.split(" (")[0], line, [], None, -2.0)
        cx, cy = 20 + (i % cols) * cell_w + cell_w / 2, 20 + (i // cols) * cell_h + cell_h / 2
        x, y = round(cx - b.size.width() / 2), round(cy - b.size.height() / 2)
        p.save()
        p.translate(x, y)
        b.paint(p, b.size.width() / 2, 1.3)
        p.restore()
    p.end()
    save(img, "bubble-styles.png")


def ask() -> None:
    """The ask box over the penguin, with an answer in it."""
    w, h, floor = 520, 470, 440
    box = AskBox()
    box.set_style(styles.get("electric"), True)
    answer = (
        "Undo the commit but keep its changes:\n\n```\ngit reset --soft HEAD~1\n```\n\n"
        "Your files stay as they are and the changes go back to being staged."
    )
    box.open(QPoint(w // 2, 300), "Ask Starry", "Enter to ask · Esc to close · answers from Claude", "Ask anything", text=answer,
             prefill="how do I undo my last git commit?", activate=False)
    box.ensurePolished()
    shot = QImage(box.width() * DPR, box.height() * DPR, QImage.Format.Format_ARGB32_Premultiplied)
    shot.setDevicePixelRatio(DPR)
    shot.fill(Qt.GlobalColor.transparent)
    box.render(shot)
    img = canvas(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    card(p, w, h, [(w / 2, floor - 40, GLOW["penguin"], 160)], floor=floor)
    sprites = Sprites(companions.COMPANIONS["penguin"].anim_dir(), 112, DPR)
    sprite = sprites.frame("idle", 0, False)
    top = floor - sprite.height()
    p.drawPixmap(QPointF(w / 2 - sprite.anchor, top), sprite.pixmap)
    p.drawImage(QPointF(round(w / 2 - box._tail_x), round(top + 4 - box.height())), shot)
    p.end()
    box.hide()
    save(img, "ask-box.png")


def portraits() -> None:
    """Each chatmon resting, on its own, for the README's table."""
    for cid in ORDER:
        sprites = Sprites(companions.COMPANIONS[cid].anim_dir(), 104, DPR)
        sprite = sprites.frame("idle", 0, False)
        img = canvas(sprite.width() + 8, sprite.height() + 8)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QPointF(4, 4), sprite.pixmap)
        p.end()
        save(img, f"chatmon-{cid}.png")


JOBS = {"portraits": portraits, "banner": banner, "social": social, "hero": hero, "agents": agents_demo, "styles": styles_sheet, "ask": ask}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for job in sys.argv[1:] or list(JOBS):
        JOBS[job]()
