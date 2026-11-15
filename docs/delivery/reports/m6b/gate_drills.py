"""M6B's gate drills: ruff and mypy pass on a copy of the tree, fail on one deliberate violation, and pass again.

usage (from the worktree root, with the venv's Python, which has ruff and mypy):
    python docs/delivery/reports/m6b/gate_drills.py [--only ID ...]

tests/drills/run.py drills pytest assertions; these drill the static gates M6B configured: one violation of each rule
family ruff gained (UP, C4, PIE, PERF, RUF, S, DTZ, BLE, C90), and a type error in a module that came off mypy's
exemption list. Each mutation is made in a temporary copy (chatmon/, packaging/, tests/ and pyproject.toml), never in
the tree; the copy's file is put back byte for byte and checked before the gate runs green again. The log
(gate-drills.log) and a JSON summary (gate-drills-results.json) are written beside this file.
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
PY = sys.executable
TAIL = 20
COPIED = ["chatmon", "packaging", "tests", "pyproject.toml"]

RUFF = [PY, "-m", "ruff", "check", "--no-cache", "."]
MYPY = [PY, "-m", "mypy", "--platform", "linux", "--no-incremental"]

# A violation appended to a phase-A module ruff's commit changed, one per family; each names the rule ruff must report.
COMPLEX = "def _drill(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(15)) + "    return -1\n"
DRILLS = [
    ("ruff-UP", RUFF, "chatmon/behavior.py", '_DRILL = "%s" % 1\n', "UP031"),
    ("ruff-C4", RUFF, "chatmon/behavior.py", "_DRILL = [v for v in (1, 2)]\n", "C416"),
    ("ruff-PIE", RUFF, "chatmon/behavior.py", "_DRILL = list(range(0, 3))\n", "PIE808"),
    ("ruff-PERF", RUFF, "chatmon/behavior.py", "def _drill(items):\n    out = []\n    for i in items:\n        out.append(i * 2)\n    return out\n", "PERF401"),
    ("ruff-RUF", RUFF, "chatmon/behavior.py", "_DRILL = list(range(3))[0]\n", "RUF015"),
    ("ruff-S", RUFF, "chatmon/behavior.py", '_DRILL = eval("1")\n', "S307"),
    ("ruff-DTZ", RUFF, "chatmon/behavior.py", "import datetime as _dt\n\n_DRILL = _dt.datetime.now()\n", "DTZ005"),
    ("ruff-BLE", RUFF, "chatmon/behavior.py", "try:\n    _DRILL = 1\nexcept Exception:\n    _DRILL = 2\n", "BLE001"),
    ("ruff-C90", RUFF, "chatmon/behavior.py", COMPLEX, "C901"),
    ("ruff-S101-in-chatmon", RUFF, "chatmon/behavior.py", "assert __name__\n", "S101"),
]
# A type error in a module that came off the exemption list (find, replace, expected diagnostic).
MYPY_DRILLS = [
    ("mypy-brains", MYPY, "chatmon/brains.py", ("MAX_REPLY = 32 * 2**20", 'MAX_REPLY: int = "32 MB"'), "Incompatible types in assignment"),
    ("mypy-winpipe", MYPY, "chatmon/winpipe.py", ("REPLY_MAX = 64 * 1024", 'REPLY_MAX: int = "64 KB"'), "Incompatible types in assignment"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)  # noqa: S603 - ruff and mypy, fixed
    return done.returncode, done.stdout + done.stderr


def tail(out: str) -> str:
    return "\n".join(out.rstrip().splitlines()[-TAIL:])


def drill(ident: str, cmd: list[str], rel: str, change, expected: str, copy: Path, log: list[str]) -> dict:
    target, tree_file = copy / rel, ROOT / rel
    original = target.read_bytes()
    result = {"id": ident, "file": rel, "command": cmd, "expected": expected, "status": "fail", "reason": None,
              "before_sha256": sha(original), "tree_sha256": sha(tree_file.read_bytes())}
    log.append(f"\n=== drill {ident} on {rel}\ncommand: {' '.join(cmd)}")
    if result["tree_sha256"] != result["before_sha256"]:
        result["reason"] = "the tree's file differs from the copy's"
        return result
    code, out = run(cmd, copy)
    result["baseline_exit"] = code
    log.append(f"-- green: exit {code}\n{tail(out)}")
    if code != 0:
        result["reason"] = "the gate isn't green on the copy"
        return result
    text = original.decode("utf-8")
    if isinstance(change, tuple):
        find, replace = change
        if text.count(find) != 1:
            result["reason"] = f"{find!r} occurs {text.count(find)} times, not once"
            return result
        mutated = text.replace(find, replace)
        result["mutation"] = f"{find!r} became {replace!r}"
    else:
        mutated = text + ("" if text.endswith("\n") else "\n") + "\n\n" + change
        result["mutation"] = f"appended {change!r}"
    try:
        target.write_bytes(mutated.encode("utf-8"))
        result["mutated_sha256"] = sha(target.read_bytes())
        code, out = run(cmd, copy)
        result["mutated_exit"] = code
        result["observed"] = next((line.strip() for line in out.splitlines() if expected in line), "")
        log.append(f"-- red: exit {code}\n{tail(out)}")
        if code == 0:
            result["reason"] = "the gate passed the violation"
        elif not result["observed"]:
            result["reason"] = f"the gate failed without naming {expected}"
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
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    chosen = [d for d in DRILLS + MYPY_DRILLS if not args.only or d[0] in args.only]
    copy = Path(tempfile.mkdtemp(prefix="chatmon-gate-drill-"))
    versions = [run([PY, "-m", tool, "--version"], ROOT)[1].strip() for tool in ("ruff", "mypy")]
    log = [f"M6B gate drills, {sys.version.split()[0]}, {'; '.join(versions)}", f"copy: {copy}"]
    results = []
    try:
        for rel in COPIED:
            src = ROOT / rel
            if src.is_dir():
                shutil.copytree(src, copy / rel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache"))
            else:
                shutil.copy2(src, copy / rel)
        results = [drill(*d, copy, log) for d in chosen]
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
