# M6A readiness, the plans round for v0.10.0 at 7816159 (2026-11-15), bound again at 56caddd

This review is the round's first ([../wave5/readiness.md](../wave5/readiness.md), at 7816159), read again at
56caddd. Its receipt went stale with the plan's new paragraph and the files below. It is a requirements review,
not proof that the code works: the behavior and red receipts are.

## Since 7816159

- **df3e93c** (the coordinator's): `chatmon/layer.py`'s two `app = QGuiApplication.instance()` lines are
  `app: QCoreApplication | None = QGuiApplication.instance()`, CONTRIBUTING.md's second workaround for 6.12.1's
  stubs, with no change at run time; CONTRIBUTING.md's opt-in table names `CHATMON_PINS_NETWORK=1`.
- **56caddd** (the coordinator's): `tests/test_app_smoke.py::test_hide_menu_and_reload` waits for the greeting
  before it hides the chatmon, and expects the "Recent messages" entry the greeting adds. The greeting could land
  inside the test's one-second spin when the companion was slow to start: the WSL failure of this round's first
  binding. The coordinator's drill ([reports/wave5/flaky-hide-menu/drill.py.txt](../../wave5/flaky-hide-menu/drill.py.txt)),
  run again here, fails the old body with the start slowed by 0.6 s and passes the new one at 0, 0.6, 1.4 and 2 s
  ([reports/wave5b/flaky-hide-menu-drill-windows.log](../../wave5b/flaky-hide-menu-drill-windows.log), and in WSL
  [reports/wave5b/flaky-hide-menu-drill-wsl.log](../../wave5b/flaky-hide-menu-drill-wsl.log)).

For this plan: df3e93c changed CONTRIBUTING.md, which T7B owns. Neither commit changes what a criterion asks or what Chatmon does: one is two type
annotations and a documentation row, the other a test's wait. Each requirement still maps both ways to its
criteria.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.

## The review at 7816159

The final round's review is [../wave4f/readiness.md](../wave4f/readiness.md) (at 45a17b3). Its receipt went stale
because files the plan binds changed (`.github/dependabot.yml`, `CONTRIBUTING.md`, `tests/test_cli.py`,
`tests/test_requirements.py`). This review re-reads the plan's obligations against the brief, the rules and the
code as they are now. It is a requirements review, not proof that the code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md), [ROADMAP.md](../../../ROADMAP.md) and `pyproject.toml`: unchanged
  since round three. The status is in [OUTCOME.md](../../../OUTCOME.md), which no plan binds.
- `.github/`: `ci.yml` and `packages.yml` unchanged since bf9d8ac (`git diff 45a17b3 7816159 -- .github/workflows/ci.yml
  .github/workflows/packages.yml` is empty). `dependabot.yml` lost both pip entries, with a comment saying why;
  `workflows/pins.yml` is new.
- `packaging/`: `pins.py`, `requirements-pins.in` and `requirements-pins.txt` are new; every other list and lock is
  unchanged.
- `CONTRIBUTING.md`: its Dependencies section (Dependabot for actions; the pins workflow and `pins.py --apply` for
  Python; relocking a Dependabot security update with uv). `SECURITY.md` and the issue chooser are unchanged.
- The tests: `tests/test_pins.py` and `tests/fake_uv.py` are new; `tests/test_requirements.py` checks
  `requirements-pins.txt` too; `tests/test_cli.py` (a plan input) gains the `chatmon ask` activation tests.
- The outcomes of the two pending operations, observed before anything was recorded: [outcomes.log](../wave5/outcomes.log).

## This plan

**M6A-02 no longer holds as written, and is replaced.** It says "Dependabot keeps github-actions and pip
dependencies up to date", and M6A-02.A1 asks for "github-actions, pip in /packaging and pip in /" in
`.github/dependabot.yml`. Dependabot's first run on `main` (P-DEPENDABOT) opened #19, #20 and #21. Each locked our
`uv pip compile --universal` lists again with pip-compile, for one platform: the macOS build's packages and nuitka's
Windows marker went missing. The owner closed all three, each with a comment saying why. PR #22 then removed both pip
entries and put `packaging/pins.py`, run weekly by `.github/workflows/pins.yml`, in their place. That was the owner's
decision and the coordinator's merge, not a failing implementation. The requirement is superseded, as the delivery
contract asks, not rewritten:

- **M6A-02B** (replacing M6A-02): Dependabot keeps github-actions up to date, and a weekly uv check
  (`packaging/pins.py`, run by `.github/workflows/pins.yml`) proposes the Python pins' updates. Both take only
  releases at least 14 days old.
  - **M6A-02B.A1** (manual): `dependabot.yml` is schema-valid; github-actions is weekly with a 14-day cooldown; there
    are no pip entries, and the file says why.
  - **M6A-02B.A2** (behavior, red): the pins check's rules, by `tests/test_pins.py` on a stand-in uv:
    - the 14-day cutoff;
    - PyQt6 6.12.0 held back with its reason;
    - PyQt6 and PyQt6-Qt6 on one release line;
    - one version per package across the locks;
    - nothing moving backwards;
    - `--apply` moving the `.in` pins and the dev extra, never the `PyQt6>=6.5` floor;
    - each list locked again with its own universal, hashed command, a one-platform lock refused.

    The nine drills of [reports/m6a/pins/](../pins/README.md) are their red checks.
  - **M6A-02B.A3** (manual): `pins.yml` is reviewed, passes CI's actionlint and zizmor, and its runs on `main`
    open one issue and then edit it, never a second.
- **T7** is superseded by **T7B**, which keeps T7's files (the Dependabot config, SECURITY.md, CONTRIBUTING.md, the
  issue chooser) and M6A-10.A1, and adds the pins check's files. The old records and their receipts stay as history.

Each new criterion is observable here or on GitHub, and says what fails. None conflicts with another requirement:
M6A-06's hash-locked builds are what `pins.py` keeps (it refuses a lock that isn't uv's universal one with hashes),
and M6A-10.A2's dev extra is what `--apply` keeps in step.

**M6A-07.A1** (a pushed tag builds, signs, attests every file, drafts the release, checks it and only then publishes)
is unchanged as a criterion. Its first tagged run is now observed, not pending (P-RELEASE, [outcomes.log](../wave5/outcomes.log)).

The other criteria (M6A-01, M6A-03 to M6A-06, M6A-08 to M6A-13, M6A-15, M6A-I1) map both ways as before. No task of
theirs owns a changed file apart from T2, whose `tests/test_requirements.py` now checks the pins lock as well.

Result: ready, with M6A-02 superseded by M6A-02B as above. No other requirement is unclear, conflicting or missing
failure behavior.
