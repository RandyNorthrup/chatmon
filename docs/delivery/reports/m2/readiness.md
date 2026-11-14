# M2 readiness review, 2026-11-14

A review of the requirements in [m2-bubbles-askbox.md](../../m2-bubbles-askbox.md) against the brief
([ASSESSMENT.md, M2](../../ASSESSMENT.md)), the rules ([ROADMAP.md](../../ROADMAP.md), `pyproject.toml`) and the code
at `5346385`. It reviews the requirements, not the implementation; behavior proof is in the test and drill logs.

## Findings re-checked in the code

Every item was traced in the code before planning; those without a ✓ in the brief were re-checked as the roadmap asks.

| Item | Re-check | Result |
|---|---|---|
| M2-01 ✓ | Probe (`probe01.py`, scratch): a counting document in `SpeechBubble` and in the ask box's browser; second text on a laid-out document | Confirmed: `loadResource` returned the file as a 61×47 pixmap for both (`bubble.py:173`, `705`), before `without_images` ran. |
| M2-02 | Probe of Qt's markdown import | Confirmed: each code line is a block with `nonBreakableLines` and `BlockCodeLanguage`; h1 gets `FontSizeAdjustment` 3. Also: indented code blocks carry `BlockCodeLanguage` without a fence, so both kinds are code. |
| M2-03 | `bubble.py:167-212` | Confirmed: no height limit; buttons laid on one row whatever their width. |
| M2-04 | `bubble.py:307` | Confirmed: one `drawText` into a 40 px box, no wrap or elision. |
| M2-05 | `styles.py:46`, `57`; `bubble.py:320-323` | Confirmed: white on `#26b8d9` is 2.4:1. New: Qt's markdown importer colours every link in the *application* palette's link colour when it reads the text (probe: `#0000ff` offscreen, `#f0d3a3` on Windows), so no style's link colour ever applied to links. |
| M2-06 | `bubble.py:776-798` | Confirmed: no `:focus` rule. |
| M2-07 | `bubble.py:94-98`, `171`, `308`, `318`, stylesheet | Confirmed: fixed point sizes, fixed widths 340 and 380. |
| M2-08 | `bubble.py:163`, `222-226` | Confirmed: `now + timeout_s`, no hover state. |
| M2-09 | `bubble.py:233-242` | Confirmed: `hit` knows close, buttons and body only. |
| M2-10 | `bubble.py:715-716` | Confirmed: `at_end` scrolls to the maximum. |
| M2-11 | `bubble.py:434-435` | Confirmed: 380 wide, answer at most 320 high. |
| M2-12 ✓ | `bubble.py:335`, `657-658` | Confirmed: `QLineEdit`, short pastes joined with spaces. |
| M2-13 | `bubble.py:151-155`, `544-548`; [perf-before.log](perf-before.log) | Confirmed: a bubble left up 30 s drew 892 frames at 0.4–4.8 ms each; `AskBox._frames` has no power-saving input. |
| M2-14 | `bubble.py:451-453`; perf-before.log | Confirmed: 169–178 child-widget paint events a second. |
| M2-15 | `bubbleart.py:997`, `1068`, `1086`, `1187-1191`, `316`, `354`; perf-before.log | Confirmed: with the notch moving, a draw costs 3–11× one with the notch still (2.1–21.5 ms against 0.2–4.4 ms). |
| M2-16 to M2-19 | `bubble.py` | Confirmed absent. |
| M2-20 | Fill sampled from each still's text area | Confirmed and worse than reported: fairy links 2.6:1 on the fill (`#fad7e3`); selected text is never given a colour, so it keeps the body colour on the accent (1.3–3.5:1 in every painted style). Also: fairy's lit-up primary button draws its label in its own fill colour, 1.0:1. |

## Clarity, conflicts and decisions

1. **`more_requested` (roadmap contract) against M2-03.** The More button belongs to the speech bubble, which the
   stage draws and which has no Qt signals. Decision: `SpeechBubble.on_more(title, markdown)`, like its `on_close`;
   recorded as a contract deviation in the plan for M7.
2. **M2-12 and naming.** The same field names the chatmon and renames chats, where a line break means nothing.
   Decision: several lines only while asking (`chatting(True)`); otherwise lines are joined, as before. The overlay's
   tests (M3's `test_overlay_stage.py`) paste "two\nlines" into a box that isn't chatting and expect one line: they stay
   true.
3. **M2-19 against callers.** `app.py` and its tests rely on `dismiss()` hiding the box at once (`isVisible()` false,
   `closed` emitted). Decision: fade out with a copy of the box in a window of its own, the box itself hidden at once.
   No fades on the Wayland overlay (the stage draws the box) or on Wayland windows (no window opacity there).
4. **"About 55%" (M2-11).** Decision: collapsed, the answer area keeps its 320 px (scaled with text size) but never
   past 55% of the screen; expanded, the whole box may reach 55% of the screen's height and 1.5× its width (within
   90% of the screen's width).
5. **"1–2 loop periods" (M2-13).** Decision: one loop period, two if one is shorter than 4 s, then the effects fade
   out over 1.2 s onto the still picture. Hover and new text start them again.
6. **Streamed text (M2-18).** `append_partial(text)` adds a chunk; `set_partial(text)` replaces it, for an `Asker` that
   reports the whole text so far (M1B decides which). `set_answer` clears it.
7. **Reading time (M2-08).** The assessment's "or until closed" and the settings tab (M7-03) need a policy object:
   `TimeoutPolicy(until_closed, factor)`. A message asked to stay (`timeout_s=None`) still stays.

## Missing failure behavior, now specified

- No `on_more` handler: the text is still capped with "…", and no More button is offered.
- Text-size factor out of range: clamped to 0.75–3.0.
- `set_busy(label, None)`: the label without seconds.
- A Copy link whose token isn't this text's: nothing is copied (an answer can write such a link itself).
- A link with any scheme other than http, https or mailto: not reported by `link_at`, never opened.
- Palette colours that fail a pair: adjusted toward black or white until they reach the ratio.

## Scope and rules

- Files: only M2's (`bubble.py`, `bubbleart.py`, `styles.py`, new `highlight.py`), one new module of M2's
  (`richtext.py`) and tests. `stagemenu.py` (M3) imports `bubble.ACCENT` and `bubble.colours`: both kept.
- Tests: real Qt objects offscreen with the `qapp` fixture; contrast computed in the tests by their own WCAG
  formula (not the module's), with known values.
- No new runtime dependency. Comments and strings in the project's voice.

## Coverage and ordering

Every requirement R-M2-01..20 has one acceptance criterion AC-M2-01..20 with behavior and red checks, and every
criterion one owning task (T-M2-01..08). Order: T-M2-01 (the security bug, first as asked), T-M2-02 (colours,
which code and focus need), T-M2-03, T-M2-04, T-M2-05, T-M2-06, T-M2-07, T-M2-08. No cycles.

## Result

Ready: no unresolved conflict; the seven decisions above are recorded in the plan's rationale or here.

## Closure re-review, 2026-11-14

The plan's narrative changed at closure, so it was reviewed again against the same brief and rules:

- **Performance budgets** were restated on counts (frames drawn, paint events, pixels composed) instead of
  wall-clock ratios. The first statement ("within 1.5x of a still notch") was a guess made before measuring; on this
  shared machine wall-clock times swing several-fold between runs (see `perf-after.log` against the earlier runs in
  the commit history), while the counts are the same on every run. No requirement or acceptance criterion changed.
- **Findings** made while building (the importer's link colour, fairy's button label, Qt 6.11's selection query,
  the exit crash shared with the base commit) are recorded in the plan; the first two are inside M2-05 and M2-20,
  the third is a fix inside M2's files that M3 should know about, the fourth is not M2's.
- **Integration, changelog and README notes** were filled in from what was built: every API named exists in the
  code at the closure commit, and the one contract deviation (`on_more` for `more_requested`) is stated.
- **Coverage** is unchanged: R-M2-01..20, AC-M2-01..20, T-M2-01..08.

Result: still ready; no requirement was rewritten to fit the implementation.
