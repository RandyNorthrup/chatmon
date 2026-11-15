"""Problem 2: the pointer events the overlay gets while the chatmon is dragged 330 px left, in steps.

    python drag_events.py COMPOSITOR FOLDER STEP_PX WAIT_S

The test's drag is STEP_PX 110 (each step farther than the subsurface's margin); a hand's, a few px each 1/60 s."""

import sys
import time

from common import chatmon_on

import sway_session
from test_sway import centre, penguin

name, folder, step_px, wait_s = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])

SPY = """
seen = []
names = {0: 'enter', 1: 'leave', 2: 'motion', 3: 'button', 4: 'axis', 5: 'frame'}
pointer = next(iter(surface.pointers.values()))[0]
real = surface.conn._handlers[pointer]
def spy(opcode, args):
    if opcode != 5:  # frames: one after each event
        seen.append(names.get(opcode, opcode))
    real(opcode, args)
surface.conn._handlers[pointer] = spy
"""

with chatmon_on(name, folder) as (desk, probe, hands):
    probe.call(SPY)
    start = penguin(probe)
    x, y = centre(start)
    hands.move(x, y)
    hands.button(sway_session.BTN_LEFT, True)
    probe.call("settled()", settle=0.1)
    print(f"{name}: pressed on the chatmon at {start}; the overlay heard {probe.call('result = seen[:]; seen.clear()')}")
    steps = round(330 / step_px)
    for step in range(1, steps + 1):
        hands.move(x - step_px * step, y)
        time.sleep(wait_s)
        got = probe.call("result = dict(seen=seen[:], held=surface._held, chatmon=list(stage._penguin.getRect()), box=box.isVisible()); seen.clear()")
        if step <= 3 or got["seen"].count("button") or step == steps:
            print(f"  step {step}: pointer at x={x - step_px * step:.0f}: {got}")
    hands.button(sway_session.BTN_LEFT, False)
    print("released:", probe.call("result = dict(seen=seen[:], held=surface._held, chatmon=list(stage._penguin.getRect()), box=box.isVisible())", settle=0.3))
