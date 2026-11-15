"""Copy a drill spec with its texts in the repository's line endings, and only the drills that still apply.

usage: python lfspec.py SPEC OUT [--skip-note NOTE.txt]

Drills written on a Windows checkout (core.autocrlf=true) carry CRLF inside multi-line `find` and `replace`
texts; git stores, and CI checks out, LF. The copy turns each CRLF into LF and keeps every other byte of each
drill. A drill whose `find` text no longer occurs `count` times in today's file is left out of the copy and named
in the note with how often it occurs, since the harness would refuse it anyway: the code it drilled has changed,
and the plan says what replaces it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CRLF, LF = chr(13) + chr(10), chr(10)


def main() -> int:
    spec, out = Path(sys.argv[1]), Path(sys.argv[2])
    note = Path(sys.argv[sys.argv.index("--skip-note") + 1]) if "--skip-note" in sys.argv else None
    data = json.loads(spec.read_text(encoding="utf-8"))
    kept, skipped = [], []
    for drill in data["drills"]:
        drill = {k: (v.replace(CRLF, LF) if k in ("find", "replace") else v) for k, v in drill.items()}
        path = Path(drill["file"])
        found = path.read_text(encoding="utf-8").count(drill["find"]) if path.exists() else -1
        (kept if found == int(drill.get("count", 1)) else skipped).append((drill, found))
    data["drills"] = [d for d, _ in kept]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + LF, encoding="utf-8", newline=LF)
    lines = [f"{spec.as_posix()}: {len(kept)} drills kept in {out.as_posix()}, {len(skipped)} left out"]
    lines += [f"  {d['id']}: its find text occurs {n} times in {d['file']} (expected {d.get('count', 1)})" for d, n in skipped]
    if note:
        with note.open("a", encoding="utf-8", newline=LF) as stream:
            stream.write(LF.join(lines) + LF)
    print(LF.join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
