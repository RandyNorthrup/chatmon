"""The plans round for v0.10.0 (7816159): each re-bound plan's drill specs, copied from its last round into wave5/.

usage: python copy_specs.py   (from the worktree's root)

Every drill is kept as it was, byte for byte in its spec's own JSON, unless its `find` text no longer occurs
exactly `count` times in today's file: then a `-v2` drill takes out the same thing in the file as it is now, and
drills-left-out.txt says which, and why. The gate-drill scripts and the other helpers are copied byte for byte, so
their logs land in wave5/ and the earlier ones stay as they were. Nothing here runs a drill.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

R = Path("docs/delivery/reports")
SOURCES = {
    "m0": ("wave4e", ["drill-spec.json", "drill-spec-new.json", "drill-spec-new2.json", "drill-spec-linux.json"]),
    "m2": ("wave4c", ["drill-spec.json"]),
    "m3": ("wave4e", ["drill-spec-r3.json", "drill-spec-wayland.json", "drill-spec-linux-r3.json", "drill-spec-wayland-linux.json"]),
    "m4a": ("wave4c", ["w4-drill-spec.json", "readers-drill-spec.json", "w4-drill-spec-linux.json", "readers-drill-spec-linux.json",
                       "w4-drill-spec-linux-qt612.json"]),
    "m6a": ("wave4f", ["drill-spec.json"]),
    "m6b": ("wave4f", ["drill-spec.json", "drill-spec-b.json", "drill-spec-linux.json"]),
    "m7": ("wave4e", ["drill-spec.json", "drill-spec-new.json", "drill-spec-v3.json"]),
    "m8": ("wave4e", ["drill-spec.json", "drill-spec-b.json", "drill-spec-c.json", "drill-spec-english.json"]),
    "m10": ("wave4f", ["drill-spec.json", "drill-spec-ci-venv.json"]),
}
HELPERS = {
    "m6a": ("wave4f", ["gate_drills.py", "sde_check.py", "distro_drill.sh"]),
    "m6b": ("wave4f", ["gate_drills.py"]),
    "m10": ("wave4f", ["gate_drills.py", "howto-replay.sh"]),
}
# The drills whose text moved with PR #22, re-aimed at the same defect in the file as it is at 7816159.
REAIMED = {
    "M0-12-ask-sent": (
        {"find": "    sent = _send({\"type\": \"ask\", \"text\": \" \".join(args)})",
         "replace": "    sent = _send({\"type\": \"say\", \"text\": \" \".join(args)})"},
        "chatmon/cli.py's ask() now keeps _send's answer (`sent = _send(...)`) to make Chatmon the active app on macOS "
        "once the box is open (212db99); the v2 drill sends the same wrong message type from the new line"),
    "M3-RC-clipboard": (
        {"find": "            board.setText(text)\n            # KWin takes a selection only",
         "replace": "            pass  # drill: the overlay's clipboard only\n            # KWin takes a selection only"},
        "chatmon/layer.py now has a second `board.setText(text)`, in _qt_window_focused (the KWin clipboard fix), so the "
        "old text occurs twice; the v2 drill takes out the same line in copy(), found by the comment that follows it"),
}


def main() -> int:
    for plan, (old, specs) in SOURCES.items():
        out = R / plan / "wave5"
        out.mkdir(parents=True, exist_ok=True)
        notes = []
        for name in specs:
            src = R / plan / old / name
            spec = json.loads(src.read_text(encoding="utf-8"))
            changed = []
            for drill in spec["drills"]:
                found = Path(drill["file"]).read_text(encoding="utf-8").count(drill["find"])
                if found == drill.get("count", 1):
                    continue
                if drill["id"] not in REAIMED:
                    raise SystemExit(f"{src}: {drill['id']}'s text occurs {found} times and has no re-aimed drill")
                change, why = REAIMED[drill["id"]]
                old_id = drill["id"]
                drill.update(change, id=old_id + "-v2")
                if Path(drill["file"]).read_text(encoding="utf-8").count(drill["find"]) != drill.get("count", 1):
                    raise SystemExit(f"{old_id}-v2's text doesn't occur once")
                changed.append(f"  {old_id} -> {old_id}-v2: {why}")
            if changed:
                (out / name).write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            else:
                shutil.copyfile(src, out / name)
            notes.append(f"{src.as_posix()}: {len(spec['drills'])} drills kept in {(out / name).as_posix()}, "
                         f"{len(changed)} re-aimed" + ("".join("\n" + c for c in changed)))
        (out / "drills-left-out.txt").write_text("\n".join(notes) + "\n", encoding="utf-8", newline="\n")
        for name in HELPERS.get(plan, (None, []))[1]:
            shutil.copyfile(R / plan / HELPERS[plan][0] / name, out / name)
        print(f"{plan}: {len(specs)} specs")
    shutil.copyfile(R / "m6a/pins/drill-spec.json", R / "m6a/wave5/drill-spec-pins.json")
    with (R / "m6a/wave5/drills-left-out.txt").open("a", encoding="utf-8", newline="\n") as notes:
        notes.write("docs/delivery/reports/m6a/pins/drill-spec.json: 9 drills kept in docs/delivery/reports/m6a/wave5/drill-spec-pins.json, "
                    "0 re-aimed (the pins check's drills, from reports/m6a/pins/, for M6A-02B)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
