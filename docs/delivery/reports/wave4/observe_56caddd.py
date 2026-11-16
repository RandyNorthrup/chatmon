"""Each CI leg's result for chosen tests of PR #24's run 43794815103 (56caddd), as a table a plan's receipts can cite.

usage: python -I observe_56caddd.py OUT PATTERN...

As observe_7816159.py, for the plans round's second binding: reads the job logs saved in docs/delivery/reports/wave5b/ci/
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

DATA = HERE.parent / "wave5b"  # the second binding's CI logs and collections (7816159's are in wave5/, read by observe_7816159.py)
CI = DATA / "ci"
FULL = DATA / "collect-56caddd.txt"
LEGS = [  # (column, log, step, collection)
    ("win3.11", "ci-133061193543-test-windows-latest-3.11.log", "Every test", FULL),
    ("win3.14", "ci-133061193481-test-windows-latest-3.14.log", "Every test", FULL),
    ("win3.15", "ci-133061193333-test-windows-latest-3.15.log", "Every test", FULL),
    ("ubu3.11", "ci-133061193373-test-ubuntu-24.04-3.11.log", "Every test", FULL),
    ("ubu3.15", "ci-133061193455-test-ubuntu-24.04-3.15.log", "Every test", FULL),
    ("arm3.14", "ci-133061193557-test-ubuntu-24.04-arm-3.14.log", "Every test", FULL),
    ("mac3.11", "ci-133061193417-test-macos-latest-3.11.log", "Every test", FULL),
    ("mac3.14", "ci-133061193442-test-macos-latest-3.14.log", "Every test", FULL),
    ("mac3.15", "ci-133063148134-test-macos-latest-3.15.log", "Every test", FULL),
    ("ubuntu", "ci-133061193482-distro-ubuntu-24.04.log", None, FULL),
    ("debian", "ci-133061193346-distro-debian-trixie.log", None, FULL),
    ("fedora", "ci-133061193474-distro-fedora-44.log", None, FULL),
    ("cocoa3.14", "ci-133061193442-test-macos-latest-3.14.log", "What Chatmon tells AppKit itself, on macOS's real window server", DATA / "collect-56caddd-macnative.txt"),
    ("winreal3.14", "ci-133061193481-test-windows-latest-3.14.log", "What Windows tells Chatmon's own windows, on its real windowing", DATA / "collect-56caddd-windows-real.txt"),
    ("gnome", "ci-133061193184-gnome.log", None, DATA / "collect-56caddd-gnome.txt"),
    ("sway", "ci-133061193363-sway.log", "The overlay on sway, and the pretend compositor's tests beside it", DATA / "collect-56caddd-sway.txt"),
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
    lines = ["# CI run 43794815103 on 56caddd (pull_request, PR #24, whose test merge has 56caddd's own tree: wave5b/ci/merge-tree.txt), all 19 jobs green on its second attempt (the first failed one test on macOS 3.15, ci-133063148134-test-macos-latest-3.15.log; its re-run passed).",
             "# Each leg's result, read from its log in docs/delivery/reports/wave5b/ci/ by cilog.py; P passed, s skipped, . not run there.",
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
