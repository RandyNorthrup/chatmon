"""Each CI leg's result for chosen tests of main's run 43778643147 (7816159), as a table a plan's receipts can cite.

usage: python -I observe_7816159.py OUT PATTERN...

As observe_45a17b3.py, for the plans round for v0.10.0: reads the job logs saved in docs/delivery/reports/wave5/ci/
and names each test's result with cilog.py (the progress characters mapped onto the collection of the same source,
checked against the run's own counts and skip lines). A test is listed when its node id contains one of the
patterns. P passed, s skipped, F failed, E error, "." where that leg doesn't run that step. Nothing here runs a test.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cilog  # noqa: E402

DATA = HERE.parent / "wave5"  # this round's CI logs and collections (45a17b3's are in wave4e/, read by observe_45a17b3.py)
CI = DATA / "ci"
FULL = DATA / "collect-7816159.txt"
LEGS = [  # (column, log, step, collection)
    ("win3.11", "ci-133010594181-test-windows-latest-3.11.log", "Every test", FULL),
    ("win3.14", "ci-133010594285-test-windows-latest-3.14.log", "Every test", FULL),
    ("win3.15", "ci-133010594207-test-windows-latest-3.15.log", "Every test", FULL),
    ("ubu3.11", "ci-133010594277-test-ubuntu-24.04-3.11.log", "Every test", FULL),
    ("ubu3.15", "ci-133010594255-test-ubuntu-24.04-3.15.log", "Every test", FULL),
    ("arm3.14", "ci-133010594390-test-ubuntu-24.04-arm-3.14.log", "Every test", FULL),
    ("mac3.11", "ci-133010594348-test-macos-latest-3.11.log", "Every test", FULL),
    ("mac3.14", "ci-133010594239-test-macos-latest-3.14.log", "Every test", FULL),
    ("mac3.15", "ci-133010594186-test-macos-latest-3.15.log", "Every test", FULL),
    ("ubuntu", "ci-133010594180-distro-ubuntu-24.04.log", None, FULL),
    ("debian", "ci-133010594133-distro-debian-trixie.log", None, FULL),
    ("fedora", "ci-133010594222-distro-fedora-44.log", None, FULL),
    ("cocoa3.14", "ci-133010594239-test-macos-latest-3.14.log", "What Chatmon tells AppKit itself, on macOS's real window server", DATA / "collect-7816159-macnative.txt"),
    ("winreal3.14", "ci-133010594285-test-windows-latest-3.14.log", "What Windows tells Chatmon's own windows, on its real windowing", DATA / "collect-7816159-windows-real.txt"),
    ("gnome", "ci-133010594083-gnome.log", None, DATA / "collect-7816159-gnome.txt"),
    ("sway", "ci-133010593918-sway.log", "The overlay on sway, and the pretend compositor's tests beside it", DATA / "collect-7816159-sway.txt"),
]
SHORT = {"passed": "P", "skipped": "s", "failed": "F", "error": "E", "xfailed": "x", "xpassed": "X"}


def collection(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if "::" in line and line.startswith("tests/")]


def main() -> int:
    out, patterns = Path(sys.argv[1]), sys.argv[2:]
    tables = []
    for column, log, step, coll in LEGS:
        tables.append((column, dict(cilog.results(collection(coll), cilog.text_lines(CI / log, step)))))
    nodes = [n for n in collection(FULL) if any(p in n for p in patterns)]
    width = max(len(c) for c, _ in tables)
    lines = ["# CI run 43778643147 on 7816159 (push to main, PR #22's merge; every job checked out 7816159 itself: wave5/ci/checkout.txt), all 19 jobs green.",
             "# Each leg's result, read from its log in docs/delivery/reports/wave5/ci/ by cilog.py; P passed, s skipped, . not run there.",
             "# legs: " + ", ".join(f"{c}={log}" + (f" [step: {step}]" if step else "") for c, log, step, _ in LEGS), ""]
    lines.append(" ".join(c.rjust(width) for c, _ in tables) + "  test")
    for node in nodes:
        lines.append(" ".join(SHORT.get(t.get(node, ""), ".").rjust(width) for _, t in tables) + "  " + node)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{out.as_posix()}: {len(nodes)} tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
