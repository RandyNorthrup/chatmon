# M6A-02B, the plans round for v0.10.0, bound again at 56caddd: Dependabot and the pins check (2026-11-15)

This round's first review is [../wave5/pins-review.md](../wave5/pins-review.md), at 7816159, with the outcome of
Dependabot's first run (P-DEPENDABOT) and M6A-02's replacement by M6A-02B, which the coordinator confirmed. Since then
`.github/` and the pins check's files are unchanged (`git diff 7816159 56caddd -- .github packaging tests/test_pins.py
tests/fake_uv.py` is empty). CONTRIBUTING.md's opt-in table now names `CHATMON_PINS_NETWORK`, the pins check's real-uv
test (df3e93c). This review reads them again at 56caddd.

- **M6A-02B.A1** (pass): `.github/dependabot.yml` validates against SchemaStore's schema, check-jsonschema 0.39.0, exit 0
  ([dependabot-schema.log](dependabot-schema.log)). Its one entry is github-actions, weekly, with a 14-day cooldown.
  There is no pip entry, and its header says why, as in the first review.
- **M6A-02B.A2**: its receipts are the pins tests and drills run again here ([pins-tests.log](pins-tests.log),
  [drills-pins.log](drills-pins.log)) and the Pins types job.
- **M6A-02B.A3** (pass): `.github/workflows/pins.yml` is as read line by line in the first review, and validates
  against SchemaStore's workflow schema ([dependabot-schema.log](dependabot-schema.log)). CI's lint job passed
  actionlint and zizmor on it at 56caddd ([../../wave5b/ci/ci-133061193403-lint.log](../../wave5b/ci/ci-133061193403-lint.log)).
  Its runs on `main` are those recorded in the first review: #23 opened once, then edited in place.
