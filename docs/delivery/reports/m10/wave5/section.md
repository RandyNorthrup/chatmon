## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 26 of its 26 passing receipts went stale, on `CONTRIBUTING.md`, `chatmon/a11y.py`, `chatmon/bubble.py`, `chatmon/macnative.py`, `tests/test_platform_events.py`, `tests/test_requirements.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 10 Windows drills, and 5 gate drills. All but 4 went green, red and green again; those couldn't run (below). main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m10/ci/observed-7816159.txt](reports/m10/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m10/wave5/readiness.md)).

**M10-03.A1 and M10-03.A3 fail on two new lines.** mypy with PyQt6 6.11's stubs finds no issues on linux, win32
and darwin ([wave5/mypy-611.log](reports/m10/wave5/mypy-611.log)). With 6.12.1's it finds two on each
([wave5/mypy-6121.log](reports/m10/wave5/mypy-6121.log)): `chatmon/layer.py:824: error: Need type annotation for
"app"  [var-annotated]`, and `:917` the same. Both are `app = QGuiApplication.instance()` in PR #22's KWin and
Hyprland fixes (6f7dd3f). 6.12.1's stubs type the static `instance()` as returning `Self`, the case of
CONTRIBUTING.md's second workaround, and these lines don't have it. CI is green because its types jobs lock
6.11's stubs; P-CI-NEXT-STUBS is the check that would catch this. The four gate drills on 6.12.1's stubs
couldn't run, since their first step, mypy green with those stubs, fails; the fifth, on 6.11's, went green, red
and green ([wave5/gate-drills.log](reports/m10/wave5/gate-drills.log)).
The how-to's replay in WSL finds the same two errors ([wave5/howto-review.md](reports/m10/wave5/howto-review.md)).
This round changes no product code, so these receipts are recorded as failing and T3-qt612-types is blocked.
Next: the coordinator gives `app` its type on both lines
(`app: QCoreApplication | None = QGuiApplication.instance()`); then the 6.12.1 runs, the gate drills and the
how-to review run again. Everything else passed: the locks (locked again, byte for byte the committed ones),
the UI Automation test in the CI-shaped venv and its red drill, and the nine drills
([wave5/locks.log](reports/m10/wave5/locks.log), [wave5/uia-ci-venv.log](reports/m10/wave5/uia-ci-venv.log)).

**Note 4, the upstream report: posted.** Others had reported the core of it on the PyQt mailing list: Veronica
Berglyd Olsen on 2026-11-14 (pyright: `pyqtSignal`'s required `arguments`, and `typing.Self` for a parent,
https://www.riverbankcomputing.com/pipermail/pyqt/2026-November/046574.html) and Dragan A. on 2026-11-15
(`typing.Self` throughout, .../046578.html). On the owner's instruction the coordinator posted the follow-up from
the owner's subscription on 2026-11-16, archived at
https://www.riverbankcomputing.com/pipermail/pyqt/2026-November/046579.html. It adds mypy 2.4.1 `--strict`'s
repro (four errors on 6.12.1, none on 6.11.0): `installEventFilter`, `removeEventFilter` and `setParent` taking
`Self`, `setParent` losing `| None`, and the static methods that return `Self`. All three pages were read again
here ([wave5/stub-report.log](reports/m10/wave5/stub-report.log), no addresses kept). It is reported, and waits
on Riverbank's fix.

**What remains, outside the criteria.** From 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check
against the next stubs (P-CI-NEXT-STUBS, integration note 2): the coordinator. The pins check proposes 6.12.1
from that day too ([reports/m6a/pins/skip-check.log](reports/m6a/pins/skip-check.log)). Note 4's report needs
nothing more from us; Riverbank's fix to the stubs is theirs.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M10 stops on M10-03.A1 and A3 at 7816159, and on P-CI-NEXT-STUBS.
