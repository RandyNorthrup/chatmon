"""Each CI leg's result for chosen tests of run 43701523023 (bf9d8ac), as a table a plan's receipts can cite.

usage: python -I observe_bf9d8ac.py OUT PATTERN...

Reads the job logs saved in docs/delivery/reports/wave4b/ci/ and names each test's result with cilog.py (the
progress characters mapped onto the collection of the same source, checked against the run's own counts and skip
lines). A test is listed when its node id contains one of the patterns. P passed, s skipped, F failed, E error,
"." where that leg doesn't run that step. Nothing here runs a test.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cilog  # noqa: E402

DATA = HERE.parent / "wave4b"  # round two's CI logs and collections (fb19cb9's are in wave4/ci/, read by observe.py)
CI = DATA / "ci"
FULL = DATA / "collect-bf9d8ac.txt"
LEGS = [  # (column, log, step, collection)
    ("win3.11", "ci-132773560206-test-windows-latest-3.11.log", "Every test", FULL),
    ("win3.14", "ci-132773560375-test-windows-latest-3.14.log", "Every test", FULL),
    ("win3.15", "ci-132773560183-test-windows-latest-3.15.log", "Every test", FULL),
    ("ubu3.11", "ci-132773560133-test-ubuntu-24.04-3.11.log", "Every test", FULL),
    ("ubu3.15", "ci-132773560297-test-ubuntu-24.04-3.15.log", "Every test", FULL),
    ("arm3.14", "ci-132773560212-test-ubuntu-24.04-arm-3.14.log", "Every test", FULL),
    ("mac3.11", "ci-132773560089-test-macos-latest-3.11.log", "Every test", FULL),
    ("mac3.14", "ci-132773560342-test-macos-latest-3.14.log", "Every test", FULL),
    ("mac3.15", "ci-132773560263-test-macos-latest-3.15.log", "Every test", FULL),
    ("ubuntu", "ci-132773560216-distro-ubuntu-24.04.log", None, FULL),
    ("debian", "ci-132773560171-distro-debian-trixie.log", None, FULL),
    ("fedora", "ci-132773560180-distro-fedora-44.log", None, FULL),
    ("cocoa3.14", "ci-132773560342-test-macos-latest-3.14.log", "What Chatmon tells AppKit itself, on macOS's real window server", DATA / "collect-bf9d8ac-macnative.txt"),
    ("winreal3.14", "ci-132773560375-test-windows-latest-3.14.log", "What Windows tells Chatmon's own windows, on its real windowing", DATA / "collect-bf9d8ac-windows-real.txt"),
    ("gnome", "ci-132773560178-gnome.log", None, DATA / "collect-bf9d8ac-gnome.txt"),
    ("sway", "ci-132773560221-sway.log", "The overlay on sway, and the pretend compositor's tests beside it", DATA / "collect-bf9d8ac-sway.txt"),
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
    lines = ["# CI run 43701523023 on bf9d8ac (pull_request, PR #18, whose test merge has bf9d8ac's own tree), every job green.",
             "# Each leg's result, read from its log in docs/delivery/reports/wave4b/ci/ by cilog.py; P passed, s skipped, . not run there.",
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
