"""Apply the pixel fixes to the animation strips, in place.

Usage: python penguin-touchup.py [anim-dir] [--force]
  anim-dir  the strips and manifest.json (default: ../../chatmon/anim)
  --force   run again on strips the manifest marks as touched up

Run it after penguin-slice.py, or on strips that predate these fixes. Each
strip it fixes gets "touchup": <version> in its manifest entry, and a strip
already marked is skipped, because the bolt halo would stack if applied twice.

The fixes, in order (see ../README.md for why):
  1. despill: pull the chroma-key green out of edge and gap pixels (every strip)
  2. walk: the lifted back foot in frames 3, 4, 7 and 8 was drawn olive or brown;
     make it charcoal like the other feet, keeping the orange claws
  3. charge: fade any lightning the sheet's cell edge cut off with a hard line
  4. charge: a thin dark halo behind the bolts that stick out past the
     body, so they still read on a light taskbar
  5. realign every frame so the body stays put (spritefix.ALIGN), then crop the
     strip to one shared frame width
Needs Pillow and numpy.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spritefix  # noqa: E402

VERSION = 1
LIFTED_FEET = {"walk": [2, 3, 6, 7]}  # 0-based frames whose lifted back foot is olive
EFFECTS = {"charge"}  # lightning that sticks out past the body: edge fade and bolt halo
KEEP = {"beam"}  # redrawn from the original and fitted by hand (size, feet); a touch-up run must not change it


def touch_up(name, strip, entry):
    frames = spritefix.split(strip, entry["frames"], entry["w"])
    notes = []
    frames = [spritefix.despill(f) for f in frames]
    for i in LIFTED_FEET.get(name, []):
        h, w = frames[i].shape[:2]
        # The lifted back foot sits low and towards the back (left) of a right-facing walk frame.
        frames[i], n = spritefix.recolour_feet(frames[i], (0, int(h * 0.76), int(w * 0.45), h))
        notes.append(f"foot {i + 1}: {n} px")
    for i, f in enumerate(frames if name in EFFECTS else []):
        frames[i], cut = spritefix.fade_cut_edges(f)
        if cut:
            notes.append(f"faded cut edge in frame {i + 1}")
    if name in EFFECTS:
        frames = [spritefix.bolt_halo(f) for f in frames]
        notes.append("bolt halo")
    frames, shifts = spritefix.realign(frames, spritefix.ALIGN[name])
    notes.append(f"shifts {shifts}")
    return spritefix.join(frames), frames[0].shape[1], notes


def main(argv):
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]
    anim = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "chatmon", "anim")
    path = os.path.join(anim, "manifest.json")
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for name, entry in manifest.items():
        if name in KEEP:
            print(f"{name}: kept as drawn, skipped")
            continue
        if entry.get("touchup", 0) >= VERSION and not force:
            print(f"{name}: already touched up, skipped")
            continue
        png = os.path.join(anim, f"{name}.png")
        strip = np.asarray(Image.open(png).convert("RGBA")).copy()
        fixed, w, notes = touch_up(name, strip, entry)
        Image.fromarray(fixed).save(png, optimize=True)
        entry["w"] = int(w)
        entry["touchup"] = VERSION
        print(f"{name}: w {w}; " + "; ".join(notes))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
