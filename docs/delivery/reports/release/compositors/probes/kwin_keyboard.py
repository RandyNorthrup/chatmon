"""Problem 1: where KWin's keyboard goes as the ask box opens on the overlay and closes, and what gives it back.

    python kwin_keyboard.py FOLDER [as-is | exclusive | remap | recreate]

as-is: the product as it is (on demand, as KWin lets it). exclusive: the overlay kept exclusive, as on sway.
remap: after the box closes, the layer surface unmapped (a null buffer), then made again. recreate: made again."""

import sys

from common import chatmon_on

from test_compositors import DESK_WINDOW
from test_sway import centre, penguin

folder, variant = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "as-is")


def windows(desk) -> list:
    return [(w["caption"] or "<overlay>", "active" if w["active"] else "-", w["layer"]) for w in desk.query()["windows"] if not w["deleted"]]


with chatmon_on("kwin", folder) as (desk, probe, hands):
    probe.call(DESK_WINDOW)
    print("desk window shown:", windows(desk))
    hands.move(300, 200)
    hands.type("ab")
    print("typed 'ab', the desk window has:", probe.call("result = desk.keys[:]"))
    if variant == "exclusive":
        probe.call("surface._on_demand_holds = False")
    hands.click(*centre(penguin(probe)))
    probe.call("until(lambda: surface._kb_focus, 5)", settle=0.2)
    print("ask box opened:", probe.call("result = dict(box=box.isVisible(), keyboard_mode=surface._kb_mode, overlay_has_keyboard=surface._kb_focus)"))
    print("  KWin's windows:", windows(desk))
    hands.key("Escape")
    print("Esc:", probe.call("until(lambda: not surface._kb_focus, 2); result = dict(box=box.isVisible(), keyboard_mode=surface._kb_mode, "
                             "overlay_has_keyboard=surface._kb_focus)", settle=0.3))
    if variant == "remap":
        probe.call("from chatmon import layer\nsurface.conn.request(surface._surface, layer.SURFACE_ATTACH, 'oii', 0, 0, 0)\n"
                   "surface.conn.request(surface._surface, layer.SURFACE_COMMIT)\nsurface._flush()", settle=0.3)
        print("unmapped:", probe.call("result = dict(overlay_has_keyboard=surface._kb_focus)", settle=0.3))
    if variant in ("remap", "recreate"):
        probe.call("surface._destroy_surface(); surface._create_surface(); settled()", settle=0.5)
        print("layer surface made again")
    print("  KWin's windows:", windows(desk))
    hands.type("c")
    print("typed 'c', the desk window has:", probe.call("result = desk.keys[:]", settle=0.3),
          "| overlay has the keyboard:", probe.call("result = surface._kb_focus"))
