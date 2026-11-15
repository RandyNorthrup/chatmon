"""Each CI leg's result for chosen tests of run 43677128712 (fb19cb9), as a table a plan's receipts can cite.

usage: python -I observe.py OUT PATTERN...

Reads the job logs saved in docs/delivery/reports/wave4/ci/ and names each test's result with cilog.py (the
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

CI = HERE / "ci"
FULL = HERE / "collect-fb19cb9.txt"
LEGS = [  # (column, log, step, collection)
    ("win3.11", "ci-132699632412-test-windows-latest-3.11.log", "Every test", FULL),
    ("win3.14", "ci-132699632366-test-windows-latest-3.14.log", "Every test", FULL),
    ("win3.15", "ci-132699632364-test-windows-latest-3.15.log", "Every test", FULL),
    ("ubu3.11", "ci-132699632531-test-ubuntu-24.04-3.11.log", "Every test", FULL),
    ("ubu3.15", "ci-132699632422-test-ubuntu-24.04-3.15.log", "Every test", FULL),
    ("arm3.14", "ci-132699632420-test-ubuntu-24.04-arm-3.14.log", "Every test", FULL),
    ("mac3.11", "ci-132699632455-test-macos-latest-3.11.log", "Every test", FULL),
    ("mac3.14", "ci-132699632411-test-macos-latest-3.14.log", "Every test", FULL),
    ("mac3.15", "ci-132699632434-test-macos-latest-3.15.log", "Every test", FULL),
    ("ubuntu", "ci-132699632400-distro-ubuntu-24.04.log", None, FULL),
    ("debian", "ci-132699632406-distro-debian-trixie.log", None, FULL),
    ("fedora", "ci-132699632424-distro-fedora-44.log", None, FULL),
    ("cocoa3.14", "ci-132699632411-test-macos-latest-3.14.log", "What Chatmon tells AppKit itself, on macOS's real window server", HERE / "collect-fb19cb9-macnative.txt"),
    ("winreal3.14", "ci-132699632366-test-windows-latest-3.14.log", "What Windows tells Chatmon's own windows, on its real windowing", HERE / "collect-fb19cb9-windows-real.txt"),
    ("gnome", "ci-132699632387-gnome.log", None, HERE / "collect-fb19cb9-gnome.txt"),
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
    lines = ["# CI run 43677128712 on fb19cb9 (workflow_dispatch on improve/assessment-fixes), every job green.",
             "# Each leg's result, read from its log in docs/delivery/reports/wave4/ci/ by cilog.py; P passed, s skipped, . not run there.",
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
