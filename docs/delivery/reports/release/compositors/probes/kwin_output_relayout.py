"""The first output unplugged on KWin: KWin moves the one left to 0,0, and the stage follows a tick later.

    python kwin_output_relayout.py FOLDER"""

import sys
import time

from common import chatmon_on

STATE = ("g = stage.screen().geometry(); result = dict(screen=stage.screen().name(), qt_screen=list(g.getRect()), stage_origin=[stage.origin().x(), stage.origin().y()], "
         "chatmon=list(stage._penguin.getRect()), behavior_x=stage.behavior.x)")

with chatmon_on("kwin", sys.argv[1], outputs=2) as (desk, probe, _hands):
    second = desk.add_output()
    print("plugged in:", desk.outputs())
    probe.call("until(lambda: len(QtGui.QGuiApplication.screens()) == 2, 5)")
    print("stage:", probe.call(STATE))
    desk.disable_output(desk.first_output())
    print("unplugged the first:", desk.outputs())
    print("stage at once:", probe.call(f"until(lambda: stage.screen() is not None and stage.screen().name() == {second!r} and surface._size is not None, 5); settled(); " + STATE, settle=0.3))
    time.sleep(1)
    print("stage 1 s later:", probe.call("settled(); " + STATE))
    shot = desk.screenshot("after", output=second)
    drawn = [x for x in range(shot.width()) if shot.pixelColor(x, 740).red() + shot.pixelColor(x, 740).green() > 30]
    print("drawn at y=740 on the output left:", (min(drawn), max(drawn)) if drawn else None)
