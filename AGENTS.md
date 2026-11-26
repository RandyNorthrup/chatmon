# Working instructions

- Always use the caveman skill for conversation. Keep code, comments and documentation in plain English.
- End each session with suggested next steps and any remaining blockers.
- Keep UI accessible and responsive, including keyboard navigation and screen-reader behavior.
- Update the documentation when behavior or maintenance commands change.
- Search existing code, callers, tests, tools and documentation before creating another implementation. Extend the canonical path.
- Verify deletions across the whole repository, including art and packaging tools. Qt overrides, native callbacks and protocol constants can look unused to static tools.
- Add meaningful regression tests for security and performance defects. Use `tests/drills/run.py` for isolated green/red/restored-green checks; never inject defects into the working tree.
- Preserve existing formatting, quality rules, privacy promises and runtime dependency policy in `CONTRIBUTING.md`.
