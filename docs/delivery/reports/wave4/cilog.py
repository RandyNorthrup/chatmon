"""Name each test's result in a pytest run's log, from its progress characters and the collection order.

usage: python -I cilog.py COLLECTION LOG [--step NAME] [--out TSV]
       python -I cilog.py COLLECTION LOG [--step NAME] --show PATTERN...

COLLECTION is `pytest --collect-only -q` of the same source (fb19cb9 here): one node id per line, in run order.
LOG is a job's log from `gh run view RUN --job JOB --log` (each line "job<TAB>step<TAB>timestamp text"), or a
plain pytest log. Without -v, pytest prints one character per test in collection order (. passed, s skipped,
F failed, E error, x xfailed, X xpassed), so the n-th character is the n-th collected test's result.

The mapping is only trusted when it checks out: the run collected as many tests as the collection lists, the
characters add up to that number, the per-file counts agree wherever the log names its files, the skips per file
agree with the run's own "SKIPPED [n] file:line" lines (pyproject.toml's -rs), and the run's summary line gives
the same totals. Any disagreement is an error (exit 2), never a guess. Nothing here runs a test.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

STAMP = re.compile(r"^(?:\N{BYTE ORDER MARK})?\d{4}-\d\d-\d\dT[\d:.]+Z ?")
PROGRESS = re.compile(r"^(?:(tests[/\x5c]\S+\.py) )?([.sFExX]+)\s*\[\s*\d+%\]\s*$")
COLLECTED = re.compile(r"collected (\d+) items?(?: / (\d+) deselected)?")
SKIP_LINE = re.compile(r"^SKIPPED \[(\d+)\] (tests[/\x5c][^:]+):\d+:")
SUMMARY = re.compile(r"^=*\s*((?:\d+ \w+(?:, )?)+) in [\d.]+s")
WORDS = {".": "passed", "s": "skipped", "F": "failed", "E": "error", "x": "xfailed", "X": "xpassed"}
BACKSLASH = chr(0x5C)  # Windows runners name test files with backslashes


def text_lines(log: Path, step: str | None) -> list[str]:
    """The log's own text, without gh's job/step columns and timestamps; only the named step's when given."""
    out = []
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = raw.split("\t", 2)
        if len(parts) == 3:
            if step is not None and parts[1] != step:
                continue
            raw = parts[2]
        elif step is not None:
            continue
        out.append(STAMP.sub("", raw).replace("\x1b[0m", "").rstrip())
    return out


def results(collection: list[str], lines: list[str]) -> list[tuple[str, str]]:
    # -q leaves out the header; then the summary line's totals have to account for every collected test.
    collected = next((COLLECTED.search(line) for line in lines if COLLECTED.search(line)), None)
    selected = None if collected is None else int(collected.group(1)) - int(collected.group(2) or 0)
    if selected is not None and selected != len(collection):
        raise SystemExit(f"cilog: the run selected {selected} tests, the collection lists {len(collection)}")
    chars: list[str] = []
    named: list[tuple[str, int]] = []  # (file, how many characters followed its name)
    for line in lines:
        match = PROGRESS.match(line)
        if not match:
            continue
        if match.group(1):
            named.append((match.group(1).replace("\\", "/"), 0))
        if named:
            named[-1] = (named[-1][0], named[-1][1] + len(match.group(2)))
        chars.extend(match.group(2))
    if len(chars) != len(collection):
        raise SystemExit(f"cilog: {len(chars)} progress characters for {len(collection)} collected tests")
    files = [node.split("::", 1)[0] for node in collection]
    if named:
        per_file = collections.Counter(files)
        for name, count in named:
            if per_file.get(name) != count:
                raise SystemExit(f"cilog: the log gives {name} {count} results, the collection {per_file.get(name)}")
    skipped_here = collections.Counter(f for f, c in zip(files, chars) if c == "s")
    skipped_said: collections.Counter[str] = collections.Counter()
    for line in lines:
        match = SKIP_LINE.match(line)
        if match:
            skipped_said[match.group(2).replace("\\", "/")] += int(match.group(1))
    # A skip raised in a helper (tests/private_bus.py) is reported at the helper's line, not the test's: every test
    # file may have fewer -rs lines than skips, never more, and the helpers' lines make up exactly the difference.
    if skipped_said:
        test_files = set(files)
        over = {f: (skipped_here.get(f, 0), n) for f, n in skipped_said.items() if f in test_files and n > skipped_here.get(f, 0)}
        short = sum(skipped_here[f] - skipped_said.get(f, 0) for f in skipped_here)
        helpers = sum(n for f, n in skipped_said.items() if f not in test_files)
        if over or short != helpers:
            raise SystemExit(f"cilog: skips per file disagree with the -rs lines: {over or (short, helpers)}")
    totals = collections.Counter(WORDS[c] for c in chars)
    summary = next((SUMMARY.match(line) for line in reversed(lines) if SUMMARY.match(line)), None)
    if summary is None:
        raise SystemExit("cilog: the log has no summary line")
    if summary:
        said = {w: int(n) for n, w in (part.split(" ", 1) for part in summary.group(1).split(", "))}
        said.pop("deselected", None)
        said = {("passed" if w == "passed" else w): n for w, n in said.items()}
        if any(totals.get(w, 0) != n for w, n in said.items() if w in WORDS.values()):
            raise SystemExit(f"cilog: the summary says {said}, the progress characters {dict(totals)}")
    return [(node, WORDS[c]) for node, c in zip(collection, chars)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("collection", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("--step", default=None, help="the job step whose pytest run to read")
    parser.add_argument("--out", type=Path, default=None, help="write node<TAB>result lines here")
    parser.add_argument("--show", nargs="+", default=None, help="print the results of tests whose id contains these")
    args = parser.parse_args(argv)
    collection = [line.strip() for line in args.collection.read_text(encoding="utf-8").splitlines()
                  if "::" in line and line.startswith("tests/")]
    table = results(collection, text_lines(args.log, args.step))
    if args.out:
        args.out.write_text("".join(f"{node}\t{word}\n" for node, word in table), encoding="utf-8", newline="\n")
    if args.show:
        for node, word in table:
            if any(p in node for p in args.show):
                print(f"{word}\t{node}")
    counts = collections.Counter(word for _, word in table)
    print(f"# {args.log.name}{' step ' + repr(args.step) if args.step else ''}: {dict(counts)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
