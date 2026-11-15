"""M10's gate drills: mypy, with PyQt6 6.12.1's stubs and with 6.11's, passes on a copy of the tree, fails on one
deliberate change, and passes again.

usage (from the worktree root):
    python docs/delivery/reports/m10/gate_drills.py NEXT_PYTHON [--only ID ...]

NEXT_PYTHON is a throwaway venv's interpreter with PyQt6 6.12.1 and mypy 2.4.1; the drills marked 6.11 use the
interpreter running this script (the shared venv: PyQt6 6.11, the lock's). tests/drills/run.py drills pytest
assertions; these drill what M10-03 changed: each way 6.12.1's stubs go wrong is fixed in one module, and the fix
taken out there must fail mypy naming the stub's error, while a real type error must still fail with 6.11's stubs.
Each change is made in a temporary copy of chatmon/ and pyproject.toml, never in the tree. The copy first gets the
integration note's changes to the wayland worker's layer.py and penguin.py (wayland-files-qt6121.diff, beside this
file), so the copy is green with 6.12.1 as the tree will be once they're made. The copy's file is put back byte for
byte and checked before mypy runs green again. The log (gate-drills.log) and a JSON summary (gate-drills-results.json)
are written beside this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
PATCH = HERE / "wayland-files-qt6121.diff"
TAIL = 12

# (id, which stubs, file, (find, replace), the diagnostic mypy must print)
DRILLS = [
    ("signal-from-qtcore", "6.12.1", "chatmon/hotkey.py",
     ("from .qtsignal import pyqtSignal\n", "from PyQt6.QtCore import pyqtSignal\n"),
     'Missing named argument "arguments" for "pyqtSignal"'),
    ("parent-unignored", "6.12.1", "chatmon/updates.py",
     ("        super().__init__(parent)  # type: ignore[arg-type]", "        super().__init__(parent)  # noqa: drill"),
     'Argument 1 to "__init__" of "QObject" has incompatible type'),
    ("constructor-untyped", "6.12.1", "chatmon/a11y.py",
     ("bus: QDBusConnection = QDBusConnection.sessionBus()", "bus = QDBusConnection.sessionBus()"),
     'Need type annotation for "bus"'),
    ("null-image-unchecked", "6.12.1", "chatmon/sprites.py",
     ("    if bits is None:  # a null image: no rows\n        return []\n", ""),
     'Item "None" of "voidptr | None" has no attribute "asstring"'),
    ("alias-mistyped", "6.11", "chatmon/qtsignal.py",
     ("= QtCore.pyqtSignal\n", "= QtCore.pyqtSlot\n"),
     "Incompatible types in assignment"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)  # noqa: S603 - mypy and git, fixed
    return done.returncode, done.stdout + done.stderr


def tail(out: str) -> str:
    return "\n".join(out.rstrip().splitlines()[-TAIL:])


def drill(ident: str, stubs: str, rel: str, change: tuple[str, str], expected: str, python: dict[str, str], copy: Path, log: list[str]) -> dict:
    cmd = [python[stubs], "-m", "mypy", "--platform", "linux", "--no-incremental"]
    target, tree_file = copy / rel, ROOT / rel
    original = target.read_bytes()
    result = {"id": ident, "stubs": f"PyQt6 {stubs}'s stubs", "file": rel, "command": cmd, "expected": expected, "status": "fail",
              "reason": None, "before_sha256": sha(original), "tree_sha256": sha(tree_file.read_bytes())}
    log.append(f"\n=== drill {ident} on {rel}, PyQt6 {stubs}\ncommand: {' '.join(cmd)}")
    if result["tree_sha256"] != result["before_sha256"]:
        result["reason"] = "the tree's file differs from the copy's"
        return result
    code, out = run(cmd, copy)
    result["baseline_exit"] = code
    log.append(f"-- green: exit {code}\n{tail(out)}")
    if code != 0:
        result["reason"] = "mypy isn't green on the copy"
        return result
    text = original.decode("utf-8")
    find, replace = change
    if text.count(find) != 1:
        result["reason"] = f"{find!r} occurs {text.count(find)} times, not once"
        return result
    result["mutation"] = f"{find!r} became {replace!r}"
    try:
        target.write_bytes(text.replace(find, replace).encode("utf-8"))
        result["mutated_sha256"] = sha(target.read_bytes())
        code, out = run(cmd, copy)
        result["mutated_exit"] = code
        result["observed"] = next((line.strip() for line in out.splitlines() if expected in line), "")
        log.append(f"-- red: exit {code}\n{tail(out)}")
        if code == 0:
            result["reason"] = "mypy passed the change"
        elif not result["observed"]:
            result["reason"] = f"mypy failed without naming {expected}"
    finally:
        target.write_bytes(original)
    result["after_sha256"] = sha(target.read_bytes())
    if result["after_sha256"] != result["before_sha256"]:
        result["reason"] = "the copy's file wasn't put back"
        return result
    if result["reason"]:
        return result
    code, out = run(cmd, copy)
    result["restored_exit"] = code
    log.append(f"-- restored green: exit {code}\n{tail(out)}")
    if code != 0:
        result["reason"] = "not green again after putting the file back"
        return result
    result["status"] = "pass"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("next_python")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    python = {"6.12.1": args.next_python, "6.11": sys.executable}
    chosen = [d for d in DRILLS if not args.only or d[0] in args.only]
    copy = Path(tempfile.mkdtemp(prefix="chatmon-m10-gate-"))
    log = [f"M10 gate drills, Python {sys.version.split()[0]}", f"copy: {copy}"]
    for stubs, exe in python.items():
        log.append(f"PyQt6 {stubs}: {exe}: {run([exe, '-c', 'import PyQt6.QtCore as q; print(q.PYQT_VERSION_STR)'], ROOT)[1].strip()}, "
                   f"{run([exe, '-m', 'mypy', '--version'], ROOT)[1].strip()}")
    results = []
    try:
        shutil.copytree(ROOT / "chatmon", copy / "chatmon", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache"))
        shutil.copy2(ROOT / "pyproject.toml", copy / "pyproject.toml")
        code, out = run(["git", "apply", "--ignore-whitespace", str(PATCH)], copy)
        log.append(f"applied {PATCH.name}: exit {code} {out.strip()}")
        if code != 0:
            raise SystemExit(f"couldn't apply {PATCH.name}: {out}")
        results = [drill(*d, python, copy, log) for d in chosen]
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    log.append("\n=== summary")
    log.extend(f"{r['status'].upper():4} {r['id']}" + (f": {r['reason']}" if r["reason"] else "") for r in results)
    (HERE / "gate-drills.log").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    (HERE / "gate-drills-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(log[-len(results) - 1:]))
    return 0 if results and all(r["status"] == "pass" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
