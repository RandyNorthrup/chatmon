"""The plans round for v0.10.0, bound again at 56caddd: the seven plans df3e93c and 56caddd staled get wave5b/ copies
of their wave5/ drill specs and helpers.

usage: python copy_specs_b.py   (from the worktree's root)

The coordinator's df3e93c (layer.py's two QGuiApplication.instance() calls typed, and CONTRIBUTING.md's opt-in
table) staled M3, M6A, M6B, M8 and M10, and 56caddd (tests/test_app_smoke.py's test_hide_menu_and_reload waits for the
greeting) M0 and M7 too. Every spec is copied byte for byte from wave5/, but M3's Wayland one: its
M3-RC-clipboard-v2 (which left the real sway's test green) is dropped and -v3 (wave5/drill-spec-wayland-linux-v3.json)
takes its place, so the drills run once each. The gate-drill scripts, sde_check.py and distro_drill.sh are copied
byte for byte (M10's is wave5/'s, which skips wayland-files-qt6121.diff); howto-replay.sh names 56caddd. Nothing here
runs a drill.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

R = Path("docs/delivery/reports")
PLANS = {
    "m0": ["drill-spec.json", "drill-spec-new.json", "drill-spec-new2.json", "drill-spec-linux.json"],
    "m7": ["drill-spec.json", "drill-spec-new.json", "drill-spec-v3.json"],
    "m3": ["drill-spec-r3.json", "drill-spec-wayland.json", "drill-spec-linux-r3.json", "drill-spec-wayland-linux.json"],
    "m6a": ["drill-spec.json", "drill-spec-pins.json", "gate_drills.py", "sde_check.py", "distro_drill.sh"],
    "m6b": ["drill-spec.json", "drill-spec-b.json", "drill-spec-linux.json", "gate_drills.py"],
    "m8": ["drill-spec.json", "drill-spec-b.json", "drill-spec-c.json", "drill-spec-english.json"],
    "m10": ["drill-spec.json", "drill-spec-ci-venv.json", "gate_drills.py", "howto-replay.sh"],
}


def main() -> int:
    for plan, names in PLANS.items():
        old, new = R / plan / "wave5", R / plan / "wave5b"
        new.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copyfile(old / name, new / name)
        shutil.copyfile(old / "context.json", new / "context.json")
        print(f"{plan}: {len(names)} files")
    wayland = R / "m3/wave5b/drill-spec-wayland-linux.json"
    spec = json.loads(wayland.read_text(encoding="utf-8"))
    v3 = json.loads((R / "m3/wave5/drill-spec-wayland-linux-v3.json").read_text(encoding="utf-8"))["drills"]
    spec["drills"] = [d for d in spec["drills"] if d["id"] != "M3-RC-clipboard-v2"] + v3
    wayland.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    howto = R / "m10/wave5b/howto-replay.sh"
    text = howto.read_text(encoding="utf-8")
    text = text.replace("and the plans round for v0.10.0 (7816159):", "and the plans round for v0.10.0 (7816159, then 56caddd):")
    text = text.replace("tracked files at 7816159 but", "tracked files at 56caddd but")
    howto.write_text(text, encoding="utf-8", newline="\n")
    (R / "m3/wave5b/drills-left-out.txt").write_text(
        "docs/delivery/reports/m3/wave5/drill-spec-wayland-linux.json: copied to wave5b/ without M3-RC-clipboard-v2 (it left the real "
        "sway's clipboard test green: wave5/drills-left-out.txt), with M3-RC-clipboard-v3 (wave5/drill-spec-wayland-linux-v3.json) in its place\n"
        "every other spec of M0, M3, M6A, M6B, M7, M8 and M10: copied from wave5/ byte for byte, every drill kept\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
