"""Narrator's own record of what it said, with Chatmon in front: Narrator on (Ctrl+Win+Enter), Chatmon's ask box
open and a hook's message (`chatmon say`), then Narrator's speech recap (Narrator key +
Alt + X), whose window lists what Narrator last spoke, read through UI Automation. Then Narrator off.
Live captions doesn't caption Narrator's own speech, so this is how Narrator's words are captured as text.

usage: narrator_recap.py OUT_DIR SOURCE_TREE SHIM
"""

import sys

sys.argv = [*sys.argv[:4], "narrator"]  # drive_windows reads OUT, SRC, SHIM and the reader from its arguments

import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import comtypes.client  # noqa: E402
import drive_windows as d  # noqa: E402

VK_INSERT, VK_MENU, VK_X = 0x2D, 0x12, 0x58
EXTENDED = 0x1


def recap_keys() -> None:
    """Insert (the Narrator key) + Alt + X, Insert sent as the extended key it is."""
    downs = [d._key(VK_INSERT, flags=EXTENDED), d._key(VK_MENU), d._key(VK_X)]
    ups = [d._key(VK_X, flags=d.KEYUP), d._key(VK_MENU, flags=d.KEYUP), d._key(VK_INSERT, flags=EXTENDED | d.KEYUP)]
    d.note(f"pressed Insert+Alt+X, Narrator's speech recap (SendInput: {d._send(*downs, *ups)})")


def texts_of(hwnd: int) -> list[str]:
    """Every name, value and text in the window, through UI Automation's raw view (the recap's text is in a text box)."""
    UIA = d.UIA
    automation = comtypes.client.CreateObject(UIA.CUIAutomation8, interface=UIA.IUIAutomation5)
    walker = automation.RawViewWalker
    found: list[str] = []

    def walk(element, depth=0):
        name = element.CurrentName
        if name:
            found.append(name)
        try:
            value = element.GetCurrentPattern(UIA.UIA_ValuePatternId)
            if value:
                text = value.QueryInterface(UIA.IUIAutomationValuePattern).CurrentValue
                if text:
                    found.append(text)
            pattern = element.GetCurrentPattern(UIA.UIA_TextPatternId)
            if pattern:
                text = pattern.QueryInterface(UIA.IUIAutomationTextPattern).DocumentRange.GetText(-1)
                if text:
                    found.append(text)
        except comtypes.COMError:
            pass
        child = walker.GetFirstChildElement(element) if depth < 16 else None
        while child:
            walk(child, depth + 1)
            child = walker.GetNextSiblingElement(child)

    walk(automation.ElementFromHandle(hwnd))
    return found


def main() -> int:
    d.note(f"Narrator speech-recap probe: Chatmon {d.VERSION} from {d.SRC}")
    d.press(d.VK_CONTROL, d.VK_LWIN, d.VK_RETURN, label="Ctrl+Win+Enter (Narrator on)")
    for _ in range(20):
        if d.narrator_running():
            break
        time.sleep(0.5)
    time.sleep(12)
    narrators = d.narrator_running()
    d.note(f"Narrator running: {narrators}")
    env = dict(d.os.environ, CHATMON_DEBUG="1", PROBE_SRC=str(d.SRC), PROBE_TRACE=str(d.OUT / "chatmon-trace.jsonl"), PROBE_QUEUE="1")
    with open(d.OUT / "chatmon-stdout.log", "w", encoding="utf-8") as console:
        app = subprocess.Popen([d.PY, str(d.SHIM)], cwd=d.SRC, env=env, stdout=console, stderr=subprocess.STDOUT, creationflags=d.BELOW_NORMAL)
    for _ in range(90):
        r = subprocess.run([d.PY, "-m", "chatmon", "status"], capture_output=True, text=True, timeout=60, cwd=d.SRC, creationflags=d.BELOW_NORMAL)
        if r.stdout.startswith("Chatmon is running."):
            break
        time.sleep(1)
    time.sleep(10)
    starts = d.traced(0, "start")
    pid = starts[0]["pid"] if starts else app.pid
    d.note(f"Chatmon running, pid {pid}")

    d.chatmon("ask")
    time.sleep(3)
    in_front = d.front()["pid"] == pid
    time.sleep(5)
    a1 = time.time()
    d.chatmon("say", "Probe one: the build finished while Chatmon was in front.")
    time.sleep(7)

    recap_keys()
    time.sleep(4)
    new = [w for w in d.windows_of(cls="NarratorSpeechRecapDialog")]
    d.note(f"windows that weren't there before (not Chatmon's): {new}")
    recap: list[str] = []
    for window in new:
        recap += texts_of(window["hwnd"])
    (d.OUT / "speech-recap.txt").write_text("\n".join(recap) + "\n", encoding="utf-8")
    d.note(f"speech recap: {len(recap)} entries read")
    d.press(d.VK_ESCAPE, label="Esc (the recap closes)")
    time.sleep(1)

    d.chatmon("quit")
    try:
        app.wait(30)
    except subprocess.TimeoutExpired:
        app.kill()
    d.press(d.VK_CONTROL, d.VK_LWIN, d.VK_RETURN, label="Ctrl+Win+Enter (Narrator off)")
    for _ in range(10):
        time.sleep(0.5)
        if not d.narrator_running():
            break
    d.note(f"Narrator running after Ctrl+Win+Enter: {d.narrator_running()}")

    joined = "\n".join(recap).lower()
    results = []
    for case, said, needle, how in (("A1", a1, "build finished", "in front: the ask box open, then `chatmon say`"),):
        trace = d.traced(said - 0.5, "announce", "uia-say", "uia-in-front", "reader")
        lines = [line for line in recap if needle in line.lower()]
        results.append({"case": case, "how": how, "chatmon_in_front": in_front, "needle": needle, "in_speech_recap": needle in joined,
                        "recap_lines": lines, "chatmon_routes": [e.get("route") for e in trace if e["event"] == "announce"], "trace": trace})
        d.note(f"CASE {case}: in Narrator's speech recap: {needle in joined}: {lines}")
    (d.OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(r["in_speech_recap"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
