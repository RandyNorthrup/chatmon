"""The VoiceOver probe: VoiceOver on, Chatmon started, Chatmon made to announce things the ways a person meets
them, and every phrase VoiceOver speaks meanwhile kept, from its own AppleScript (`content of last phrase`, polled).

usage: drive_voiceover.py OUT_DIR SOURCE_TREE SHIM
Pass "proposed" (round 5): Chatmon with both proposed changes applied by the shim (run_chatmon.py): held
announcements posted 2.5 s after Chatmon becomes active (PROBE_SETTLE_MS), and the ask box's title handing keyboard
focus to its entry (PROBE_TITLE_PROXY). Earlier rounds ran "shipped" (Chatmon as it is) and settle passes. After each announcement
VoiceOver is left alone for 8 s, so its next phrase shows whether it went on to something else first.
Writes OUT_DIR/voiceover-phrases.jsonl (each new last phrase, when first seen), driver.log (each step), results.json
(each case: what was expected, whether VoiceOver said it, and when), transcript.txt (steps and phrases in order), and
screenshots. Chatmon's trace goes to OUT_DIR/chatmon-trace-<pass>.jsonl.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

OUT, SRC, SHIM = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
VERSION = re.search(r'__version__ = "([^"]+)"', (SRC / "chatmon" / "__init__.py").read_text(encoding="utf-8")).group(1)
LAST_PHRASE = 'tell application "VoiceOver" to get content of last phrase'
FRONT = ('tell application "System Events"\nset p to first application process whose frontmost is true\n'
         'return (name of p) & " " & (unix id of p)\nend tell')
SHORTCUT = 'tell application "System Events" to key code 49 using {command down, shift down}'  # Chatmon's Ctrl+Shift+Space
timeline: list[tuple[float, str]] = []
_log = open(OUT / "driver.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115


def stamp(t: float) -> str:
    return time.strftime("%H:%M:%S", time.gmtime(t)) + f".{int(t % 1 * 1000):03d}Z"


def note(text: str) -> None:
    t = time.time()
    timeline.append((t, text))
    line = f"{stamp(t)} {text}"
    print(line, flush=True)
    _log.write(line + "\n")


def run(args: list[str], timeout: float = 60, show: str | None = None) -> subprocess.CompletedProcess:
    note("$ " + (show or " ".join(args)))
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=SRC)
    out = (r.stdout + r.stderr).strip()
    note(f"  exit {r.returncode}" + (": " + out.replace("\n", " | ") if out else ""))
    return r


def chatmon(*args: str) -> subprocess.CompletedProcess:
    shown = " ".join(a if re.fullmatch(r"[\w.-]+", a) else json.dumps(a) for a in args)
    return run([PY, "-m", "chatmon", *args], show=f"python -m chatmon {shown}")


def osa(script: str, timeout: float = 15) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def act(script: str, label: str = "") -> str:
    code, out, err = osa(script)
    note(f"osascript ({label or script}): exit {code}" + (f", {out}" if out else "") + (f", {err}" if err else ""))
    return out


def front() -> str:
    code, out, err = osa(FRONT)
    said = out if code == 0 else f"unknown ({err})"
    note(f"frontmost app: {said}")
    return said


def shot(name: str) -> None:
    subprocess.run(["screencapture", "-x", str(OUT / f"screen-{name}.png")], capture_output=True, timeout=30)


class Heard(threading.Thread):
    """VoiceOver's last phrase, asked for again and again; each new one kept with when it was first seen."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.phrases: list[tuple[float, str]] = []
        self.polls = self.errors = 0
        self.stopping = False
        self.file = open(OUT / "voiceover-phrases.jsonl", "a", encoding="utf-8", buffering=1)  # noqa: SIM115

    def run(self) -> None:
        last = None
        while not self.stopping:
            code, text, err = osa(LAST_PHRASE, timeout=5)
            t = time.time()
            self.polls += 1
            if code == 0 and text != last:
                last = text
                self.phrases.append((t, text))
                self.file.write(json.dumps({"t": round(t, 3), "at": stamp(t), "phrase": text}, ensure_ascii=False) + "\n")
            elif code != 0:
                self.errors += 1
                if self.errors <= 5 or self.errors % 100 == 0:
                    note(f"VoiceOver's last phrase couldn't be read ({code}): {err}")
            time.sleep(0.05)

    def find(self, needle: str, since: float, until: float | None = None) -> tuple[float, str] | None:
        return next(((t, x) for t, x in self.phrases if t >= since and (until is None or t <= until) and needle.lower() in x.lower()), None)

    def wait_for(self, needle: str, since: float, seconds: float) -> tuple[float, str] | None:
        end = time.time() + seconds
        while time.time() < end:
            found = self.find(needle, since)
            if found:
                return found
            time.sleep(0.1)
        return self.find(needle, since)


class Pass:
    """One run of Chatmon: started, its cases, quit."""

    def __init__(self, name: str, settle_ms: int, heard: Heard, title_proxy: bool = False) -> None:
        self.name, self.settle_ms, self.heard, self.title_proxy = name, settle_ms, heard, title_proxy
        self.trace = OUT / f"chatmon-trace-{name}.jsonl"
        self.app: subprocess.Popen | None = None

    def start(self) -> float:
        env = dict(os.environ, CHATMON_DEBUG="1", PROBE_SRC=str(SRC), PROBE_TRACE=str(self.trace), PROBE_SETTLE_MS=str(self.settle_ms),
                   PROBE_TITLE_PROXY="1" if self.title_proxy else "")
        with open(OUT / f"chatmon-stdout-{self.name}.log", "w", encoding="utf-8") as console:
            self.app = subprocess.Popen([PY, str(SHIM)], cwd=SRC, env=env, stdout=console, stderr=subprocess.STDOUT)
        started = time.time()
        note(f"Chatmon started from source through run_chatmon.py (pass {self.name}, PROBE_SETTLE_MS={self.settle_ms}, PROBE_TITLE_PROXY={int(self.title_proxy)}), pid {self.app.pid}")
        for _ in range(90):
            r = subprocess.run([PY, "-m", "chatmon", "status"], capture_output=True, text=True, timeout=60, cwd=SRC)
            if r.stdout.startswith("Chatmon is running."):
                break
            time.sleep(1)
        note(f"python -m chatmon status: {r.stdout.splitlines()[0] if r.stdout else r.stderr.strip()}")
        return started

    def quit(self) -> None:
        chatmon("quit")
        try:
            self.app.wait(30)
        except subprocess.TimeoutExpired:
            self.app.kill()
        note(f"Chatmon exited: {self.app.returncode}")

    def traced(self, since: float) -> list[dict]:
        lines = self.trace.read_text(encoding="utf-8").splitlines() if self.trace.exists() else []
        wanted = ("announce", "voiceover-say", "voiceover-post", "app-state", "hypothesis", "focus")
        return [e for e in map(json.loads, lines) if e["t"] >= since and e["event"] in wanted]

    def active(self) -> bool:
        return str(self.app.pid) in front().split()[-1:]

    def to_front_by_system_events(self) -> None:
        act(f'tell application "System Events" to set frontmost of (first application process whose unix id is {self.app.pid}) to true',
            "System Events: Chatmon frontmost, as Cmd-Tab or the Dock would")

    def focused(self) -> str:
        script = (f'tell application "System Events"\nset p to first application process whose unix id is {self.app.pid}\n'
                  'set f to value of attribute "AXFocusedUIElement" of p\nset r to ""\n'
                  'try\nset r to r & (role of f)\nend try\ntry\nset r to r & " | " & (description of f)\nend try\n'
                  'try\nset r to r & " | value: " & (value of f)\nend try\nreturn r\nend tell')
        code, out, err = osa(script)
        said = out if code == 0 else f"unknown ({err})"
        note(f"Chatmon's focused element: {said}")
        return said

    def to_finder(self) -> None:
        if not self.active():  # the ask box may still be open behind: Esc reaches it only with Chatmon in front
            self.to_front_by_system_events()
            time.sleep(1.5)
        act('tell application "System Events" to key code 53', "Esc")
        time.sleep(1)
        act('tell application "Finder" to activate', "Finder activate")
        time.sleep(3)
        front()


results: list[dict] = []


def record(p: Pass, case: str, how: str, expected: str, needle: str, said_at: float, *, fronted_at: float | None = None,
           wait: float = 15, extra: dict | None = None, linger: float = 8) -> dict:
    got = p.heard.wait_for(needle, said_at, wait)
    entry = {
        "pass": p.name, "case": case, "how": how, "expected_words": expected, "needle": needle, "said_at": stamp(said_at),
        "heard": bool(got), "spoken": got[1] if got else None, "spoken_at": stamp(got[0]) if got else None,
        "seconds_after_said": round(got[0] - said_at, 2) if got else None, **(extra or {}),
    }
    if got:
        # "last phrase" says what VoiceOver started to say. Nothing more is done for `linger` seconds, so the next
        # phrase VoiceOver starts of its own accord bounds how much of this one it said before moving on.
        time.sleep(max(0.0, got[0] + linger - time.time()))
        later = [(t, x) for t, x in p.heard.phrases if t > got[0]]
        entry["words"] = len(got[1].split())
        entry["next_phrase"] = (round(later[0][0] - got[0], 2), later[0][1]) if later else None
        entry["quiet_after_for_at_least"] = None if later else linger
    if fronted_at is not None:
        early = p.heard.find(needle, said_at, fronted_at)
        entry.update(brought_to_front_at=stamp(fronted_at), held_while_behind=early is None,
                     seconds_after_front=round(got[0] - fronted_at, 2) if got else None)
    entry["trace"] = p.traced(said_at - 0.5)
    entry["phrases_meanwhile"] = [(stamp(t), x) for t, x in p.heard.phrases if said_at - 0.5 <= t <= time.time()]
    results.append(entry)
    note(f"CASE {p.name}/{case}: " + (f"VoiceOver said {got[1]!r} {entry['seconds_after_said']} s after" if got else "VoiceOver never said it")
         + (f"; held while behind: {entry['held_while_behind']}" if fronted_at is not None else ""))
    return entry


def held_case(p: Pass, case: str, how: str, send, expected: str, needle: str, bring: str) -> None:
    """Chatmon behind (Finder in front), something to say comes, then Chatmon is brought forward by `bring`."""
    note(f"== {p.name}/{case}: {how}")
    p.to_finder()
    said = time.time()
    send()
    time.sleep(10)  # held, if it's held
    shot(f"{p.name}-{case}-behind")
    fronted = time.time()
    if bring == "shortcut":
        act(SHORTCUT, "Cmd+Shift+Space, Chatmon's shortcut")
    elif bring == "chatmon ask":
        chatmon("ask")
    else:
        p.to_front_by_system_events()
    time.sleep(2.5)
    activated = p.active()
    entry = record(p, case, how, expected, needle, said, fronted_at=fronted, extra={"chatmon_active_after_bringing": activated})
    shot(f"{p.name}-{case}-front")
    if not entry["heard"] and not activated:
        note(f"{case}: Chatmon didn't become the active app; now through System Events, to see whether the held words come then")
        again = time.time()
        p.to_front_by_system_events()
        time.sleep(2)
        record(p, case + "+SE", how + "; then System Events makes it frontmost", expected, needle, said, fronted_at=again,
               extra={"chatmon_active_after_bringing": p.active()})


def typing(p: Pass, case: str) -> None:
    note(f"== {p.name}/{case}: Finder in front; the shortcut opens the ask box; `version` typed, Return")
    p.to_finder()
    act(SHORTCUT, "Cmd+Shift+Space, Chatmon's shortcut")
    time.sleep(3)
    activated = p.active()
    time.sleep(4)
    before = p.focused()
    said = time.time()
    act('tell application "System Events" to keystroke "version"', "keystroke version")
    time.sleep(1)
    after = p.focused()
    shot(f"{p.name}-{case}-typed")
    act('tell application "System Events" to key code 36', "Return")
    record(p, case, ("HYPOTHESIS: " if p.title_proxy else "") + "in front (the shortcut opened the ask box): `version` typed, Return", f"I'm Chatmon {VERSION}.", f"Chatmon {VERSION}",
           said, extra={"chatmon_active_after_shortcut": activated, "focused_before_typing": before, "focused_after_typing": after})
    time.sleep(1)
    shot(f"{p.name}-{case}-answered")


def proposed(heard: Heard) -> None:
    """Both proposed changes at once, as the shim applies them: held announcements posted 2.5 s after Chatmon becomes
    active, and the ask box's title handing keyboard focus to the entry."""
    p = Pass("proposed", 2500, heard, title_proxy=True)
    act('tell application "Finder" to activate', "Finder activate")
    time.sleep(2)
    greeting(p, p.start())
    time.sleep(3)
    typing(p, "A2")
    in_front(p, "A1")
    held_case(p, "B1", "HYPOTHESIS: behind: `chatmon say`; then Chatmon's shortcut opens the ask box",
              lambda: chatmon("say", "Probe P-B1, held while Chatmon is behind."), "Chatmon. Probe P-B1, held while Chatmon is behind.",
              "Probe P-B1", "shortcut")
    typing(p, "A2-after-B1")
    held_case(p, "C1", "HYPOTHESIS: behind: an agent's needs-you alert; then System Events makes Chatmon frontmost (no ask box)",
              lambda: chatmon("notify", "needs-you", "--source", "claude", "--message", "Probe P-C1, waiting for your approval."),
              "Claude needs you. Probe P-C1, waiting for your approval. To answer, type “OK” in the chat.", "Probe P-C1", "system events")
    time.sleep(2)
    p.quit()


HELD_CASES = (
    ("B1", "behind: `chatmon say`; then Chatmon's shortcut opens the ask box", "say", "shortcut"),
    ("B3", "behind: `chatmon say`; then System Events makes Chatmon frontmost (no ask box)", "say", "system events"),
    ("C1", "behind: an agent's needs-you alert; then System Events makes Chatmon frontmost (no ask box)", "alert", "system events"),
    ("C2", "behind: an agent's needs-you alert; then Chatmon's shortcut opens the ask box", "alert", "shortcut"),
)


def held_cases(p: Pass, prefix: str) -> None:
    for case, how, kind, bring in HELD_CASES:
        tag = f"Probe {prefix}{case}"
        if kind == "say":
            text = f"{tag}, held while Chatmon is behind."
            expected = f"Chatmon. {text}"

            def send(text=text):
                chatmon("say", text)
        else:
            text = f"{tag}, waiting for your approval."
            expected = f"Claude needs you. {text} To answer, type “OK” in the chat."

            def send(text=text):
                chatmon("notify", "needs-you", "--source", "claude", "--message", text)
        held_case(p, case, ("HYPOTHESIS: " if p.settle_ms else "") + how, send, expected, tag, bring)


def greeting(p: Pass, started: float) -> None:
    record(p, "G", ("HYPOTHESIS: " if p.settle_ms else "") + "Chatmon just started (active, as launched): its greeting",
           "Hi, I'm Chatmon! Click me to ask anything.", "Hi, I'm Chatmon", started, wait=20)


def in_front(p: Pass, case: str) -> None:
    note(f"== {p.name}/{case}: Finder in front; Chatmon's shortcut opens the ask box; a hook's message comes")
    p.to_finder()
    act(SHORTCUT, "Cmd+Shift+Space, Chatmon's shortcut")
    time.sleep(3)
    activated = p.active()
    time.sleep(5)  # VoiceOver says where it's landed first
    text = f"Probe {case}, said while Chatmon is in front."
    said = time.time()
    chatmon("say", text)
    record(p, case, "in front (the shortcut opened the ask box), then `chatmon say`", f"Chatmon. {text}", f"Probe {case}", said,
           extra={"chatmon_active_after_shortcut": activated})
    shot(f"{p.name}-{case}")


def shipped(heard: Heard) -> None:
    p = Pass("shipped", 0, heard)
    greeting(p, p.start())
    shot("shipped-G")
    in_front(p, "A1")
    typing(p, "A2")
    time.sleep(2)
    p.quit()


def settled(heard: Heard, ms: int) -> None:
    p = Pass(f"settle-{ms}", ms, heard)
    act('tell application "Finder" to activate', "Finder activate")
    time.sleep(2)
    greeting(p, p.start())
    time.sleep(3)
    held_cases(p, f"S{ms // 100}-")
    time.sleep(2)
    p.quit()


def main() -> int:
    note(f"probe started: Chatmon {VERSION} from {SRC}, Python {sys.version.split()[0]}")
    run(["sw_vers"])
    run(["/System/Library/CoreServices/VoiceOver.app/Contents/MacOS/VoiceOverStarter"])
    deadline = time.time() + 120
    while True:
        code, out, err = osa(LAST_PHRASE)
        if code == 0:
            note(f"VoiceOver answers its AppleScript; last phrase so far: {out!r}")
            break
        if time.time() > deadline:
            note(f"VoiceOver never answered its AppleScript: {err}")
            return 2
        time.sleep(1)
    heard = Heard()
    heard.start()
    time.sleep(5)
    front()
    try:
        proposed(heard)
    finally:
        time.sleep(2)
        heard.stopping = True
        heard.join(10)
        note(f"VoiceOver's last phrase was read {heard.polls} times ({heard.errors} failed); {len(heard.phrases)} phrases kept")
        osa('tell application "VoiceOver" to quit')
        (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        events = sorted([(t, f"   [step] {x}") for t, x in timeline] + [(t, f"VO SAID: {x}") for t, x in heard.phrases])
        (OUT / "transcript.txt").write_text("".join(f"{stamp(t)} {x}\n" for t, x in events), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in results:
        note(f"{r['pass']}/{r['case']}: heard={r.get('heard')} spoken={r.get('spoken')!r}"
             + (f" held_while_behind={r['held_while_behind']}" if "held_while_behind" in r else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
