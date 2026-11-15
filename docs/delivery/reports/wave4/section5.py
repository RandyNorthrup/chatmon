"""The final round, M6A's section: M6B's and M10's wave4f/readiness.md and section.md: python section5.py ID...

Both plans bind M6A's plan, so M6A's new section stales every receipt of theirs, and each was bound a second time in
this round on checks run again (wave4f/). Their texts are the first binding's (wave4e/), with the links to their own
evidence moved to wave4f/, and a paragraph saying why they were bound again. The section keeps the first binding's
heading, so it replaces that section in the plan rather than adding a second one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
AGAIN = (
    "**Bound twice in this round.** This plan binds M6A's plan, which gained its final-round section after this plan's\n"
    "first binding (W4E-). A plan's prose is in every receipt's scope, so that staled every W4E- receipt here. Every\n"
    "check was run again on 45a17b3 ([wave4f/](reports/{plan}/wave4f/), with the suite in\n"
    "[reports/wave4f/suite-windows.log](reports/wave4f/suite-windows.log): {counts}), and bound as W4F-, with the same\n"
    "results. The W4E- receipts are kept as stale history."
)


def counts() -> str:
    log = (REPORTS / "wave4f/suite-windows.log").read_text(encoding="utf-8", errors="replace")
    return re.findall(r"(\d+ passed, \d+ skipped)", log)[-1]


def moved(text: str, plan: str) -> str:
    text = text.replace(f"reports/{plan}/wave4e/", f"reports/{plan}/wave4f/")
    text = text.replace("](reports/wave4e/suite-windows.log)", "](reports/wave4f/suite-windows.log)")
    text = text.replace("[wave4e/", "[wave4f/").replace("../m10/wave4e/", "../m10/wave4f/")
    return text.replace("reports/m6a/wave4e/mypy", "reports/m6a/wave4f/mypy").replace("reports/m10/wave4e/mypy", "reports/m10/wave4f/mypy")


def main() -> int:
    for plan in sys.argv[1:]:
        old = REPORTS / plan / "wave4e"
        new = REPORTS / plan / "wave4f"
        section = moved((old / "section.md").read_text(encoding="utf-8"), plan)
        head, receipts = section.split("\n**Receipts.**", 1)
        receipts = receipts.replace("The stale ones are kept as history, with their hashes untouched; the W4E- receipts replace",
                                    "The stale ones are kept as history, with their hashes untouched; the W4F- receipts replace")
        section = head.rstrip("\n") + "\n\n" + AGAIN.format(plan=plan, counts=counts()) + "\n\n**Receipts.**" + receipts
        (new / "section.md").write_text(section, encoding="utf-8", newline="\n")
        ready = (old / "readiness.md").read_text(encoding="utf-8")
        ready = ready.replace("# " + ready.splitlines()[0][2:], ready.splitlines()[0] + " (after M6A's section)", 1)
        ready = ready.replace("Round three's review is [../wave4c/readiness.md](../wave4c/readiness.md) (at 3586a0d). Its receipt went stale\n"
                              "because files the plan's criteria bind changed.",
                              "This round's first review is [../wave4e/readiness.md](../wave4e/readiness.md), and round three's\n"
                              "[../wave4c/readiness.md](../wave4c/readiness.md) (at 3586a0d). The first went stale when M6A's plan, an\n"
                              "input of this one, gained its final-round section.")
        assert "This round's first review" in ready, plan
        (new / "readiness.md").write_text(ready, encoding="utf-8", newline="\n")
        print(f"{plan}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
