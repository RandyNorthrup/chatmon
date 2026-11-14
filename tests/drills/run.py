"""Red drills: prove that a test notices the defect it guards against.

usage: python tests/drills/run.py SPEC.json [--only ID ...] [--log PATH] [--python EXE] [--keep]

SPEC.json:

    {"drills": [{"id": "M2-01-image", "requirement": "M2-01",
                 "file": "chatmon/bubble.py",
                 "find": "return QImage()", "replace": "return super().loadResource(kind, url)",
                 "test": ["tests/test_bubble_styles.py::test_answers_never_load_images"],
                 "expect": ["test_answers_never_load_images"]}]}

Each drill runs in a temporary copy of the repository (the tracked and untracked-but-not-ignored files, without
art/ and docs/), never in the working tree:

1. green: the named tests pass on the copy, and at least one test ran;
2. red: `find` is replaced by `replace` in `file` (it must occur exactly `count` times, 1 by default), and the
   same tests must fail with pytest's "tests failed" exit (1) and print every `expect` string;
3. restored: the file's original bytes are put back (always, even after an error), checked by SHA-256, and the
   tests must pass again.

The working tree's copy of each drilled file must match the copy's original bytes, so the hashes recorded in the
log match the source a receipt names. The log has every command, exit code, hash and the tail of each run's
output; a JSON summary is written next to it. Exit 0 only when every selected drill went green, red, green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXCLUDED_TOP = ("art/", "docs/")  # big, and no test reads them
RUN_TIMEOUT_S = 900
TAIL_LINES = 60
PYTEST_FAILED = 1  # pytest's exit code for "tests ran and some failed"; 2-5 are interruptions, errors and no tests


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_root() -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def copy_tree(root: Path, dest: Path) -> int:
    listed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8").split("\0")
    copied = 0
    for rel in listed:
        if not rel or rel.startswith(EXCLUDED_TOP):
            continue
        src = root / rel
        if not src.is_file():
            continue  # deleted in the working tree but still in the index
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    return copied


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(cwd),
        "QT_QPA_PLATFORM": env.get("QT_QPA_PLATFORM", "offscreen"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    try:
        done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        return -1, f"TIMEOUT after {RUN_TIMEOUT_S}s\n{exc.stdout or ''}{exc.stderr or ''}"
    return done.returncode, done.stdout + done.stderr


def passed_count(output: str) -> int:
    match = re.search(r"(\d+) passed", output)
    return int(match.group(1)) if match else 0


def tail(output: str) -> str:
    return "\n".join(output.rstrip().splitlines()[-TAIL_LINES:])


def load_spec(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    drills = data.get("drills") if isinstance(data, dict) else None
    if not isinstance(drills, list) or not drills:
        raise ValueError(f"{path}: needs a non-empty \"drills\" list")
    seen = set()
    for d in drills:
        for key in ("id", "file", "find", "replace", "test", "expect"):
            if key not in d:
                raise ValueError(f"{path}: drill {d.get('id', '?')} has no {key!r}")
        if d["id"] in seen:
            raise ValueError(f"{path}: drill id {d['id']} appears twice")
        seen.add(d["id"])
        if d["find"] == d["replace"]:
            raise ValueError(f"{path}: drill {d['id']} replaces its text with itself")
        if isinstance(d["expect"], str):
            d["expect"] = [d["expect"]]
        if not d["test"] or not d["expect"]:
            raise ValueError(f"{path}: drill {d['id']} needs tests and expected output")
    return drills


def drill(d: dict, root: Path, copy: Path, python: str, log: list[str]) -> dict:
    rel = d["file"]
    work_file, tree_file = copy / rel, root / rel
    cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *d["test"]]
    result = {"id": d["id"], "requirement": d.get("requirement"), "file": rel,
              "mutation": {"find": d["find"], "replace": d["replace"]}, "command": cmd,
              "expected": d["expect"], "status": "fail", "reason": None}
    log.append(f"\n=== drill {d['id']} ({d.get('requirement') or 'no requirement'}) on {rel}")
    log.append("command: " + " ".join(cmd))
    original = work_file.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    result["before_sha256"] = before
    if sha256(tree_file) != before:
        result["reason"] = "the working tree's file differs from the copy; re-run the drill"
        return result

    code, out = run(cmd, copy)
    result["baseline_exit"] = code
    log.append(f"-- green: exit {code}, {passed_count(out)} passed\n{tail(out)}")
    if code != 0 or passed_count(out) == 0:
        result["reason"] = "baseline is not green (or no test ran)"
        return result

    text = original.decode("utf-8")
    found = text.count(d["find"])
    want = int(d.get("count", 1))
    if found != want:
        result["reason"] = f"mutation text occurs {found} times, expected {want}"
        return result
    try:
        work_file.write_bytes(text.replace(d["find"], d["replace"]).encode("utf-8"))
        result["mutated_sha256"] = sha256(work_file)
        code, out = run(cmd, copy)
        result["mutated_exit"] = code
        log.append(f"-- red: exit {code}\n{tail(out)}")
        missing = [e for e in d["expect"] if e not in out]
        observed = next((line.strip() for line in out.splitlines() if any(e in line for e in d["expect"])), "")
        result["observed"] = observed
        if code != PYTEST_FAILED:
            result["reason"] = f"mutated run exited {code}, not {PYTEST_FAILED} (tests failed)"
        elif missing:
            result["reason"] = f"mutated run did not print {missing}"
    finally:
        work_file.write_bytes(original)
    after = sha256(work_file)
    result["after_sha256"] = after
    if after != before:
        result["reason"] = "restoration failed: the file's bytes differ from the original"
        return result
    if result["reason"]:
        return result

    code, out = run(cmd, copy)
    result["restored_exit"] = code
    log.append(f"-- restored green: exit {code}, {passed_count(out)} passed\n{tail(out)}")
    if code != 0:
        result["reason"] = "restored run is not green"
        return result
    result["status"] = "pass"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--only", nargs="+", default=None, help="drill ids to run")
    parser.add_argument("--log", type=Path, default=None, help="log file (default: next to the spec)")
    parser.add_argument("--python", default=sys.executable, help="interpreter with PyQt6 and pytest")
    parser.add_argument("--keep", action="store_true", help="keep the temporary copy, for debugging")
    args = parser.parse_args(argv)

    try:
        drills = load_spec(args.spec)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"drills: {exc}", file=sys.stderr)
        return 2
    if args.only:
        unknown = set(args.only) - {d["id"] for d in drills}
        if unknown:
            print(f"drills: no drill named {sorted(unknown)}", file=sys.stderr)
            return 2
        drills = [d for d in drills if d["id"] in args.only]

    root = repo_root()
    log_path = args.log or args.spec.with_suffix(".log")
    copy = Path(tempfile.mkdtemp(prefix="chatmon-drill-"))
    log: list[str] = [f"red drills from {args.spec}", f"python: {args.python}", f"copy: {copy}"]
    results: list[dict] = []
    try:
        log.append(f"copied {copy_tree(root, copy)} files")
        code, out = run([args.python, "-c", "import chatmon; print(chatmon.__file__)"], copy)
        if code != 0 or not Path(out.strip().splitlines()[-1]).resolve().is_relative_to(copy.resolve()):
            print(f"drills: the copy's chatmon is not the one imported:\n{out}", file=sys.stderr)
            return 2
        for d in drills:
            results.append(drill(d, root, copy, args.python, log))
    finally:
        if not args.keep:
            shutil.rmtree(copy, ignore_errors=True)

    failed = [r for r in results if r["status"] != "pass"]
    log.append("\n=== summary")
    for r in results:
        log.append(f"{r['status'].upper():4} {r['id']}" + (f": {r['reason']}" if r["reason"] else ""))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log) + "\n", encoding="utf-8")
    log_path.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("\n".join(log[-len(results) - 1:]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
