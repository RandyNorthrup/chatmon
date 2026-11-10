"""The companions you can pick: each one's strips are there and load, the penguin's are untouched,
and an unknown choice is the penguin."""

import hashlib
import json
import tomllib
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage

from chatmon import companions, paths, styles
from chatmon.settings import DEFAULTS, load_config
from chatmon.sprites import SIDE_VIEWS, Sprites

ROOT = Path(__file__).resolve().parent.parent
PENGUIN = companions.COMPANIONS["penguin"]
CREATURES = [c for c in companions.COMPANIONS.values() if c.id != "penguin"]
PENGUIN_MANIFEST = json.loads((PENGUIN.anim_dir() / "manifest.json").read_text(encoding="utf-8"))
# The penguin's art as approved (sha1 of every file in chatmon/anim): adding companions must not touch it.
PENGUIN_SHA1 = {
    "alert.png": "f73ec04b54d74f978bc5d0de32ad1f5c61e09779",
    "beam.png": "5ce9870f66a9f7cbadd850a05d716355a34a66d4",
    "charge.png": "dc47ff049b4904c3e1663481fbd27e4231f3349e",
    "hop.png": "a8e0891dfb85d547477ed11801ea42387840d724",
    "idle.png": "e14d4777a7397261a210b170fa980f3706481673",
    "manifest.json": "1497b64ec2a9a50866db34e1c2ccc8458c086436",
    "peek.png": "94257d9798d1d245a8d1b5b0f2901690da6cbcba",
    "sleep.png": "80c732f254cdf1d4b1cafe36834e08b3d6044a2c",
    "talk.png": "57a425aad68387dc8c515f9b1f0f52bb27d03d0e",
    "think.png": "0a4c81b869601c2a10fb2908d694d61d82b31e2c",
    "turn.png": "ceb176e6aa5902085fb02e22abf764b2e2e198b0",
    "walk.png": "96e7b72ac8e2e29b03ff900c10b66d79373dcc72",
    "wave.png": "829e6d3116e6e8f532ed386d252d42faa68b1efc",
}
OPAQUE = 32  # alpha above which a pixel shows


def manifest(companion: companions.Companion) -> dict:
    return json.loads((companion.anim_dir() / "manifest.json").read_text(encoding="utf-8"))


def frames(companion: companions.Companion, anim: str) -> list[QImage]:
    m = manifest(companion)[anim]
    strip = QImage(str(companion.anim_dir() / f"{anim}.png")).convertToFormat(QImage.Format.Format_RGBA8888)
    return [strip.copy(i * m["w"], 0, m["w"], m["h"]) for i in range(m["frames"])]


def rgba(img: QImage) -> bytes:
    assert img.bytesPerLine() == 4 * img.width()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return bytes(ptr)


def stored_sha1(path: Path) -> str:
    """The sha1 of a file as git stores it. A checkout on Windows turns the manifest's line endings into CRLF,
    so the bytes on disk differ by platform; git keeps LF, and so does this."""
    data = path.read_bytes()
    if path.suffix != ".png":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(data).hexdigest()


def test_the_penguins_files_are_untouched():
    found = {p.name: stored_sha1(p) for p in PENGUIN.anim_dir().iterdir() if p.is_file()}
    assert found == PENGUIN_SHA1


def test_the_five_companions_and_their_bubble_styles():
    assert {c.id: c.bubble_style for c in companions.COMPANIONS.values()} == {
        "penguin": "electric",
        "fire-red-panda": "fire",
        "ghost-rabbit": "ghost",
        "fairy-axolotl": "fairy",
        "leaf-pangolin": "leaf",
    }
    assert all(c.bubble_style in styles.STYLES for c in companions.COMPANIONS.values())
    assert PENGUIN.nickname == "Penguin" and len({c.nickname for c in companions.COMPANIONS.values()}) == 5
    assert PENGUIN.anim_dir() == paths.anim_dir()  # the penguin's strips stay where they were


@pytest.mark.parametrize("companion", CREATURES, ids=lambda c: c.id)
def test_a_companions_manifest_has_the_penguins_twelve_animations(companion):
    m = manifest(companion)
    assert list(m) == list(PENGUIN_MANIFEST)
    for name, entry in m.items():
        ours = PENGUIN_MANIFEST[name]
        assert (entry["frames"], entry["fps"], entry["loop"], entry["h"]) == (ours["frames"], ours["fps"], ours["loop"], ours["h"]), name
        assert 0 < entry["anchor"] < entry["w"] and 0.2 < entry["scale"] < 1.5, name


@pytest.mark.parametrize("companion", CREATURES, ids=lambda c: c.id)
def test_a_companions_strips_are_the_size_its_manifest_says(companion):
    for name, entry in manifest(companion).items():
        strip = QImage(str(companion.anim_dir() / f"{name}.png"))
        assert not strip.isNull(), name
        assert (strip.width(), strip.height()) == (entry["frames"] * entry["w"], entry["h"]), name


@pytest.mark.parametrize("companion", CREATURES, ids=lambda c: c.id)
def test_nothing_is_clipped_at_a_frames_edge(companion):
    for name in manifest(companion):
        for i, frame in enumerate(frames(companion, name)):
            data, w, h = rgba(frame), frame.width(), frame.height()
            border = data[3 : 4 * w : 4] + data[4 * w * (h - 1) + 3 :: 4] + data[3 :: 4 * w] + data[4 * w - 1 :: 4 * w]
            assert max(border) <= OPAQUE, f"{name} frame {i + 1}"


@pytest.mark.parametrize("companion", CREATURES, ids=lambda c: c.id)
def test_the_idle_breath_differs_from_the_first_frame(companion):
    """Frame 2 is the breath: the body a little taller, the feet where they were."""
    first, breath = (rgba(f) for f in frames(companion, "idle")[:2])
    changed = sum(1 for i in range(0, len(first), 4) if max(abs(first[i + c] - breath[i + c]) for c in range(4)) > 64)
    assert changed >= 80, f"only {changed} pixels differ"


@pytest.mark.parametrize("companion", list(companions.COMPANIONS.values()), ids=lambda c: c.id)
def test_the_app_loads_every_companions_sprites(qapp, companion):
    sprites = Sprites(companion.anim_dir(), 120)
    m = manifest(companion)
    assert set(sprites.anims()) == set(PENGUIN_MANIFEST)
    for name, (count, _fps, _loop) in sprites.anims().items():
        for mirror in (False, True):
            for i in range(count):
                frame = sprites.frame(name, i, mirror)
                assert frame.width() > 0 and frame.outline and 0 < frame.anchor < frame.width(), (name, i, mirror)
        left, right = sprites.frame(name, 0, False), sprites.frame(name, 0, True)
        assert (left is right) == (name not in SIDE_VIEWS)  # side views are mirrored to face left
        if "anchor" in m[name]:  # the manifest says where the floor pins the frame
            assert left.anchor == round(m[name]["anchor"] * m[name]["scale"] * 120 / m[name]["h"])
            assert right.anchor == left.width() - left.anchor or name not in SIDE_VIEWS


def test_companions_stand_about_as_tall_as_the_penguin(qapp):
    """Siblings, not giants or dwarfs: the idle frame's drawn height is within a fifth of the penguin's."""

    def drawn_height(companion) -> int:
        frame = Sprites(companion.anim_dir(), 120).frame("idle", 0, False)
        rows = [r for r in frame.outline]
        return max(r.bottom() for r in rows) - min(r.top() for r in rows) + 1

    penguin = drawn_height(PENGUIN)
    for companion in CREATURES:
        assert 0.8 * penguin <= drawn_height(companion) <= 1.2 * penguin, companion.id


def test_an_unknown_companion_is_the_penguin(tmp_path, monkeypatch):
    assert companions.get("dragon") is PENGUIN and companions.get(None) is PENGUIN and companions.get("") is PENGUIN
    assert companions.get(" Ghost-Rabbit ").id == "ghost-rabbit"
    # one whose strips are not installed is the penguin too, rather than a crash at start-up
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "anim_dir", lambda: tmp_path)
    assert companions.get("ghost-rabbit") is PENGUIN


def test_settings_default_to_the_penguin_and_a_matching_bubble(tmp_path):
    assert DEFAULTS["companion"] == "penguin" and DEFAULTS["bubble_style"] == "match"
    path = tmp_path / "config.toml"
    path.write_text('companion = "leaf-pangolin"\nbubble_style = "electric"\n', encoding="utf-8")
    config, error = load_config(path)
    assert error is None and config["companion"] == "leaf-pangolin" and config["bubble_style"] == "electric"


def test_every_companions_strips_are_packaged():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["chatmon"]
    assert {"anim/*.png", "anim/manifest.json", "anim/*/*.png", "anim/*/manifest.json"} <= set(data)
