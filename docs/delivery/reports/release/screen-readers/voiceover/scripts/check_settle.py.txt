import os, re, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
app = QApplication([])
from chatmon import a11y
src = open(sys.argv[2], encoding="utf-8").read()
block = src.split('if sys.platform == "darwin" and SETTLE_MS:')[1].split('\nif sys.platform == "darwin":')[0]
ns = {"a11y": a11y, "time": time, "os": os, "SETTLE_MS": 1000, "note": lambda *a, **k: None}
exec("if True:" + block, ns)
def pump(s):
    end = time.monotonic() + s
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)
active, posted = [True], []
q = a11y.VoiceOver(post=lambda t, i: posted.append((round(time.monotonic() - t0, 2), t, i)), active=lambda: active[0], speak=lambda t: None)
t0 = time.monotonic()
q.say("greeting")            # made while active: held for the first second
pump(0.3); assert posted == [], posted
pump(1.0); assert [p[1] for p in posted] == ["greeting"], posted
q.say("now")                 # settled: at once
assert posted[-1][1] == "now"
active[0] = False; q.state_changed(Qt.ApplicationState.ApplicationInactive)
q.say("behind", True); assert q.held == [("behind", True)]
active[0] = True; q.state_changed(Qt.ApplicationState.ApplicationActive)
assert posted[-1][1] == "now"; pump(0.5); assert posted[-1][1] == "now"
pump(0.8); assert posted[-1][1:] == ("behind", True), posted
print("hypothesis logic ok:", posted)
