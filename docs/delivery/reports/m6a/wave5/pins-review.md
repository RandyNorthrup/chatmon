# M6A-02 and M6A-02B, the plans round for v0.10.0: Dependabot and the pins check at 7816159 (2026-11-15)

The final round's review of `.github/dependabot.yml` is in [../wave4f/ci-review.md](../wave4f/ci-review.md) (at
45a17b3). This review reads the file again at 7816159, with what replaced its pip entries, and the outcome of
Dependabot's first run on `main` (P-DEPENDABOT). Every observation of GitHub below is in
[outcomes.log](outcomes.log) and [../../wave5/github-settings.txt](../../wave5/github-settings.txt), read-only, and
every job log in [../../wave5/ci/](../../wave5/ci/).

## M6A-02.A1, as written: fails at 7816159

M6A-02.A1 asks that "github-actions, pip in /packaging and pip in / are each updated weekly with a 14-day cooldown,
the PyQt6 packages move together, and the PyQt6>=6.5 floor is never raised just because a newer release exists".
At 7816159 `.github/dependabot.yml` validates against SchemaStore's schema
([dependabot-schema.log](dependabot-schema.log)). But it has one entry, github-actions, and no pip entry. The check,
run again, fails on "pip in /packaging and pip in /".

That is the owner's decision, not a regression:

- **Dependabot's first run.** `dependabot.yml` reached `main` with PR #18's merge (65ed989), and Dependabot's runs at
  2026-11-15T20:11:30Z opened #19, #20 and #21 (`app/dependabot`).
  - #19 (`/`, the qt group) moved PyQt6 to 6.12.0, which the `/packaging` entry ignores on purpose. It moved the
    `.in` pins without locking the `.txt` files again.
  - #20 and #21 were the same nuitka 4.3.1 → 4.3.4, once per entry. Each locked `packaging/requirements.txt` again
    with pip-compile, for one platform, and dropped the macOS build's packages and nuitka's Windows marker.
- **Closed by the owner.** The owner closed all three between 20:16:23Z and 20:16:29Z, each with a comment saying why.
  No Dependabot pull request is open. Dependabot's run at 7816159 (43778648374) succeeded and opened none.
- **Replaced.** PR #22 (merged as 7816159) took both pip entries out and put `packaging/pins.py`, run by
  `.github/workflows/pins.yml`, in their place. Its evidence is in [../pins/README.md](../pins/README.md).

So M6A-02 is superseded by M6A-02B ([readiness.md](readiness.md)), and M6A-02.A1's receipt here records the failure
as history.

## M6A-02B.A1: Dependabot keeps the actions only (pass)

`.github/dependabot.yml` at 7816159 (blob `fe4b6fd7`, the same on `main`):

- **Schema.** It validates against SchemaStore's Dependabot schema, check-jsonschema 0.39.0, exit 0
  ([dependabot-schema.log](dependabot-schema.log)).
- **The one entry.** `package-ecosystem: github-actions`, `directory: /`, `interval: weekly`,
  `cooldown: default-days: 14`, one group for every action (lines 14-22).
- **No pip entry, and why.** The header (lines 1-11) says each `packaging/requirements*.txt` is a
  `uv pip compile --universal` lock that Dependabot can't make. It says the Python pins move with pins.yml instead,
  and that Dependabot's alerts and security updates, repository settings, still come.
- **Settings.** Alerts (204) and security updates (`enabled`) are on
  ([../../wave5/github-settings.txt](../../wave5/github-settings.txt)).

## M6A-02B.A2: the pins check's rules (see its own receipts)

The Windows suite ([../../wave5/suite-windows.log](../../wave5/suite-windows.log)) ran `tests/test_pins.py` and
`tests/test_requirements.py`. pins.yml's types job steps were also run here on 7816159
([pins-tests.log](pins-tests.log)), and in CI on `main` (Pins run 43778643021, job types:
[../../wave5/ci/pins-133010593575-types.log](../../wave5/ci/pins-133010593575-types.log), `mypy --strict` "Success: no
issues found in 1 source file" for linux, win32 and darwin, then 28 passed, 1 skipped, the opt-in real-uv test). The
nine drills of [../pins/](../pins/README.md) went green, red and green on 7816159 ([drills-pins.log](drills-pins.log)).
Those are its behavior and red receipts; this review doesn't stand in for them.

## M6A-02B.A3: the pins workflow (pass)

`.github/workflows/pins.yml` at 7816159 (blob `3f7e1fb3`, the same on `main`), read line by line:

| What the criterion asks | Where, and what was observed | Result |
|---|---|---|
| Runs `pins.py` weekly and on dispatch | `schedule: "37 6 * * 1"` and `workflow_dispatch` (11-13); the `pins` job runs only for those two events (63) | pass |
| `contents: read` and `issues: write` only | `permissions: {}` at the top (25); `pins` has `contents: read` and `issues: write` (66-68), `types` `contents: read` (40-41); both checkouts `persist-credentials: false` (45, 75) | pass |
| uv installed hash-locked | `pip install --require-hashes -r packaging/requirements-pins.txt` (79) | pass |
| One issue: opened when something can move, edited by later runs, closed when nothing can | The step looks for an open issue with the title that github-actions opened (102-104). It edits it, or opens one, when `pins.py` exits 3, and closes it when it exits 0 (111-119). Any other exit fails the run before the issue is touched (87-90). | pass |
| ...and on `main` it does | Dispatched run 43778713259 (00:09:43Z, success) found nuitka 4.3.1 → 4.3.4 with PyQt6 6.12.0 held back, and opened #23, "Python pins ready to move", as `app/github-actions`, at 00:10:09Z ([../../wave5/ci/pins-133010817108-pins.log](../../wave5/ci/pins-133010817108-pins.log)). Dispatched run 43778794994 (00:10:29Z, success) found the same. It edited #23: GitHub's record shows `lastEditedAt` 00:11:03Z by `github-actions` ([../../wave5/ci/pins-133011060825-pins.log](../../wave5/ci/pins-133011060825-pins.log)). No second issue: one issue by that title exists, #23, open. | pass |
| The types job: `mypy --strict` on `pins.py` for linux, win32 and darwin, and the pins tests, on pull requests and pushes that touch them | `types` (36-60), on the paths `*checked` (15-23). Pins run 43778643021, the push of 7816159, ran it and passed, as above. | pass |
| actionlint and zizmor pass on it | CI run 43778643147, job lint: actionlint (with shellcheck) passed; zizmor v1.31.1 "completed .github/workflows/pins.yml" with no finding, and the job succeeded ([../../wave5/ci/ci-133010594152-lint.log](../../wave5/ci/ci-133010594152-lint.log)). It also validates against SchemaStore's workflow schema ([dependabot-schema.log](dependabot-schema.log)). | pass |

Result: M6A-02.A1 fails as written, by the owner's decision recorded above. M6A-02B.A1 and M6A-02B.A3 pass.
