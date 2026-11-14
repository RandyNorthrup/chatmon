# M2: bubbles and the ask box

The work unit for items M2-01 to M2-20 of [ASSESSMENT.md](ASSESSMENT.md#m2-bubbles-and-the-ask-box-bubblepy-bubbleartpy-stylespy-new-highlightpy),
ordered and bounded by [ROADMAP.md](ROADMAP.md). Branch `wave1/m2`, from `improve/assessment-fixes` at `5346385`.
Reports, logs and the timing script are in [reports/m2](reports/m2/).

## Rationale

Speech bubbles and the ask box are where every answer is read. The assessment found one security bug (M2-01: an
answer could make Qt read a file, and on Windows open an SMB connection) and nineteen problems of reading,
accessibility and drawing cost. This milestone fixes them inside the files M2 owns, and adds the APIs the app
needs (M7 wires them).

**Scope.** `chatmon/bubble.py`, `chatmon/bubbleart.py`, `chatmon/styles.py`, new `chatmon/highlight.py`, new
`chatmon/richtext.py`, and their tests. Nothing else is edited: what the stage (`penguin.py`, M3) or the app
(`app.py`, M0/M7) must do is in [Integration notes](#integration-notes).

**Non-goals.** Wiring the new signals into the app (M7); the stage's own use of hover, links and the hosted fade
(M3); translation of the new strings (M8); new runtime dependencies (none are added).

**Reuse decisions.**

- Markdown stays Qt's own importer (`QTextDocument.setMarkdown`), now with `MarkdownNoHTML` and a document class
  that refuses every resource. `without_images` is kept and moved with the rest of the safe-text code into
  `richtext.py`, which both bubbles share (it was in `bubble.py`; nothing outside imported it).
- Colours stay data in `styles.py`. Each style gains its measured fill, link, selection and lit-up button text;
  the plain style resolves the desktop palette. WCAG contrast is computed by a small function there (`contrast`),
  and `readable` adjusts palette colours that fall short, so high contrast themes pass as they are.
- The entry field becomes a `QTextEdit` subclass that keeps `QLineEdit`'s calls the app, the overlay and the
  tests use (`text`, `setText`, `insert`, `selectAll`, `clear`, `end`, `setSelection`, `returnPressed`,
  `hasSelectedText`, `selectedText`, `paste_requested`, `edit_menu`), so `app.py` and `penguin.py` need no change
  for it.
- The art cache in `bubbleart.py` is split, not replaced: the composed picture is cached per size with the
  notch's band composed separately per notch place; the border's geometry (`Rim`) is cached per size.
- Code highlighting is a `QSyntaxHighlighter` (in Qt already) in new `highlight.py`: formats are drawn, not stored,
  so copying, `toPlainText` and `toMarkdown` are unchanged.

**Contract deviation (recorded for M7).** The roadmap lists `more_requested` on the ask box. The More button the
assessment asks for (M2-03) is on the speech bubble, which has no signals (the stage draws it); it is delivered as
the callback `SpeechBubble.on_more(title, markdown)`, in the style of its existing `on_close`. The ask box has no
`more_requested`.

**Performance budgets** (this machine, offscreen, measured by [perf_bubbles.py](reports/m2/perf_bubbles.py)
against the base commit, run back to back: [perf-before.log](reports/m2/perf-before.log),
[perf-after.log](reports/m2/perf-after.log)). Wall-clock times swing while other workers' suites run here, so the
budgets are on counts that don't: a speech bubble left up a minute draws one or two loops of animation plus the
settle fade (1780 frames before; now 216–275, and 1025 for the leaf, whose one loop is a 34 s caterpillar walk);
the animated ask box's widgets get no paint events from its animation (170 a second before; the 4 left are the
field's blinking caret); a moving notch composes at most a third of the art's pixels it did (215–482 thousand per
draw before; now 57–118), and the picture above the notch's band once per size.

**Found on the way.**

- Qt's markdown importer colours links in the application palette's link colour when it reads the text, so no
  style's link colour ever reached a link (folded into M2-05 and M2-20).
- Fairy's lit-up first button drew its label in its own fill colour, 1.0:1 (folded into M2-05).
- Qt 6.11's text edits answer the input-method selection query with a type PyQt can't convert. The Wayland
  overlay asks it each frame (`penguin.Hosted.selected_text`); with a `QTextEdit` focused (the new field, or the
  answer area, already a `QTextBrowser`, in `show_notes`) the error in its timer stops the app. Both of the box's
  text widgets now answer with plain text (`bubble.PlainSelection`); M3 may guard the call as well.
- Ad hoc scripts that create and drop many ask boxes in one process on the Windows platform plugin can crash at
  interpreter exit; the base commit does too (checked with the same script), so it isn't M2's. Tests delete
  their boxes with `deleteLater`, as the app keeps its one box for its lifetime.

## Acceptance overview

Each requirement below is one assessment item, with its acceptance in the ledger. Every criterion is checked by
automated tests (behavior) and at least one red drill in [drill-spec.json](reports/m2/drill-spec.json) (results:
[drills.log](reports/m2/drills.log) and [drills.json](reports/m2/drills.json) for the full run, 49 of 50;
[drills-rerun.log](reports/m2/drills-rerun.log) for M2-01-images-left, whose first find text didn't match the
file's line endings). The whole suite on the final source: [final-pytest.log](reports/m2/final-pytest.log),
648 passed and 59 skipped (514 and 59 before); [final-ruff.log](reports/m2/final-ruff.log).

## Integration notes

APIs M2 delivered, and what M3 (the stage) and M7 (the app) must wire. Nothing outside M2's files was changed.

**Speech bubble (`bubble.SpeechBubble`)**

| API | What it does | Who wires it |
|---|---|---|
| `timeout_policy = TimeoutPolicy(until_closed=False, factor=1.0)` | Reading time: at least 4 s + 0.3 s a word or the asked timeout, times `factor`; or until closed. Applies from the next `show`. | M7, from the Accessibility tab (M7-03). |
| `set_hovered(on, now=None)` | Pauses expiry while hovered (the hovered time is added back) and wakes the effects. `now` defaults to the clock last given to `show`/`tick`. | M3: `Stage.move` calls `set_hovered(target is not None)` for anything on the bubble; `pointer_left` calls `set_hovered(False)`. |
| `on_more: (title, markdown) -> None` | Set it to get a **More** button when the text is cut at `max_height`. Delivered instead of the roadmap's `more_requested` (the bubble has no signals). | M7: `stage.bubble.on_more = lambda t, m: ask_box.show_notes(stage.head_point(), t, m)`. |
| `max_height` | px; default 40% of the primary screen. | M3: set to 40% of the stage's own screen when it changes screens. |
| `hit(pos)` may return `"link"`; `link_at(pos) -> QUrl or None`; `open_link_at(pos) -> bool` | Links are clickable; only http, https and mailto. | M3: in `Stage.release`, `elif target == "link": self.bubble.open_link_at(pos - box.topLeft())`; a "pointer" cursor over links in `move`. |
| `set_text_scale(f)` | 0.75–3.0, on top of the desktop font (text never smaller than it). | M7, text-size setting. |
| `set_power_saving(on)` | The still picture only. | M7: `_power_saving` calls it with `ask_box.set_power_saving`. |
| `anim_key(now)` | Now -1 once the effects settle: the stage stops redrawing by itself. | Nothing to do. |

The stage's accessible description (`a11y.spoken` in `Stage.show_message`) lists the caller's buttons only; a
**More** button added for cut text isn't in it (M3 can read `bubble.buttons` after `show`).

**Ask box (`bubble.AskBox`)**

| API | What it does | Who wires it |
|---|---|---|
| `stop_requested()` | Stop pressed while busy. | M7 cancels the `Asker` (M7-01). |
| `copy_requested(str)` | Copy clicked for an answer or a code block; the box doesn't touch the clipboard. | M7: `QGuiApplication.clipboard().setText(t)`, or `stage.clipboard_copy(t)` on the overlay (M7-10). |
| `expand_changed(bool)`, `set_expanded(bool)`, `expanded` | The bigger-box toggle; `set_expanded` restores a saved choice. | M7 may remember it. |
| `set_busy(label, started_at=None)` | "<label> is answering… N s" (from `time.monotonic()`) and Stop; `None` hides it. | M7 at ask start and finish. |
| `append_partial(text)`, `set_partial(text)` | Streamed text under the chat (a chunk, or the whole text so far); `set_answer` replaces it. | M7 from `Asker.partial` (M1B). |
| `set_text_scale(f)`, `set_reduced_motion(on)`, `set_power_saving(on)` | Text size; no fades; still picture. | M7 (M7-03, M7-11). |
| `chatting(on)` | Now also makes the field take several lines (on) or one (off: names). | Unchanged calls. |

The field (`AskBox.entry`, class `Entry`) is now a `QTextEdit`. No name the app, the overlay or the tests use was
removed: `text`, `setText`, `insert`, `end`, `setSelection`, `selectAll`, `clear`, `hasSelectedText`,
`selectedText`, `returnPressed`, `paste_requested`, `edit_menu`, `isVisible`, `setFocus` all work as before. New:
`set_multiline`, `lines`, `resized`, `MAX_LINES`. Because it isn't a `QLineEdit` any more, `penguin.Hosted.insert`
no longer joins a paste's lines for it; the field joins them itself when it's one line (names) and keeps them when
asking, as M2-12 wants. M3 can drop that `QLineEdit` check.

Other notes for M7:

- The hint should mention the new key: "Enter to ask · Shift+Enter for a new line · Esc to close".
- Chat turns are found by the transcript's own convention, a paragraph starting `**You:**` (`app._transcript`):
  keep it. A question's line breaks are lost when `_transcript` writes it as one markdown paragraph; write them as
  hard breaks (a backslash before each newline) for multi-line questions to show as typed.
- On the Wayland overlay the box doesn't fade (the stage draws it); M3 could fade the hosted proxy.
- Links in the answer area are coloured as the text is drawn: after a palette or high-contrast change, call
  `set_style` again (M7-11) so the plain style's colours are re-read.

**Styles (`styles.py`)**: `Style.colours(palette=None) -> Colours` (every resolved colour, with `ButtonLook`s);
`contrast`, `readable`, `luminance`, `mix`, `blend`. `Style` gained `fill`, `link`, `selection`, `selection_text`;
`Button` gained a fourth field, `hover_text`. The plain style's own colour fields are empty (palette). `PLAIN_ACCENT`
and `bubble.ACCENT`/`bubble.colours` remain for the stage's menus (`stagemenu.py`); M3 could take
`styles.get("plain").colours().accent` there for high contrast.

**New modules**: `richtext.py` (`SafeDocument`, `MARKDOWN`, `set_markdown`, `render`, `without_images`): anything
else that shows answer markdown should go through it. `highlight.py` (`CodeHighlighter`, `code_colours`).

**`bubbleart.py`**: `BubbleArt.paint(..., effects=1.0)` takes the effects' strength; `composed`, `rim_only` and
`rim_line` return the picture in two parts, drawn with `BubbleArt.draw`; `notch_mask` became `mask_notch`.

**Pending CI checks** (run on Linux and macOS by the coordinator): all new test files; on macOS the field's native
edit menu (`test_app_smoke.py`'s cocoa tests run with the new `Entry`); fonts differ there, which the focus-outline
and code-font tests depend on.

## Changelog notes

- **Security:** an answer can no longer make Chatmon read a file on your computer or reach a network share by
  naming it as a picture or in HTML. Pictures in answers show as "[image]" and HTML shows as text.
- Long messages fit on the screen: they end in "…" with a **More** button, buttons wrap onto another row, and long
  titles wrap.
- Bubbles stay long enough to read (at least 4 seconds plus a little for each word) and wait while you point at
  them. Links in them can be clicked.
- Code blocks wrap instead of running off the bubble, on a tinted panel, with keywords, strings, comments and
  numbers coloured to match the bubble style. Headings stay a sensible size.
- The ask box takes several lines: Shift+Enter starts a new one, and pasted text keeps its line breaks. A long chat
  opens at your newest question, turns are separated by a line, and a button makes the box bigger.
- Every answer and code block has a **Copy** link, and an answer on its way shows who is answering, for how long,
  and a **Stop** button (once the app wires them up).
- Every bubble style meets WCAG AA contrast (4.5:1) for text, links, selections and buttons. The plain style uses
  your desktop's colours, high contrast themes included. Fairy's highlighted button label could not be seen.
- Every control in the ask box shows a clear focus outline, and text follows your desktop's font size.
- The ask box fades in and out, unless reduced motion is on.
- Animated bubble edges play for a loop and then rest, starting again when you point at the bubble, so Chatmon
  uses less power while a message sits on screen.

## README notes

- Privacy and security: answers can't make Chatmon open files or network locations; pictures in answers are
  shown as "[image]" and HTML as plain text.
- The ask box: Enter sends, Shift+Enter starts a new line; the ⤢ button makes the box bigger; **Copy** under an
  answer or a code block; **Stop** while an answer is coming.
- Bubbles: point at a bubble to keep it up; **More** opens a long message in full.
- Accessibility: all bubble styles meet WCAG AA contrast; the plain style follows the desktop's theme, high
  contrast included; focus outlines are visible; text follows the desktop font size (and a text-size setting,
  once M7 adds it); reduced motion turns off the ask box's fades.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M2",
    "title": "Bubbles and the ask box",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    }
  },
  "requirements": [
    {
      "id": "R-M2-01",
      "statement": "Answers can never make Chatmon read a file: every bubble document returns an empty resource for every URL, markdown is set with MarkdownNoHTML, and images are removed before drawing.",
      "priority": "critical",
      "acceptance": [
        "AC-M2-01"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-02",
      "statement": "Code blocks wrap, on a tinted padded panel, and heading sizes are capped.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-02"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-03",
      "statement": "Speech bubbles are at most about 40% of the screen high, with an ellipsis and a More button for the rest, and their buttons wrap onto more rows.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-03"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-04",
      "statement": "Titles wrap onto a second line and are elided past it, with their height measured.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-04"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-05",
      "statement": "The plain style takes Highlight, HighlightedText, Link, Button and ButtonText from the palette, and every style's text and link pairs reach 4.5:1.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-05"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-06",
      "statement": "History, New chat, Expand, close, attach, chips, Stop and the field show a 2 px focus outline.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-06"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-07",
      "statement": "Text is the larger of its size and the app font, scaled by an optional text-size factor, and widths derive from font metrics.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-07"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-08",
      "statement": "Bubbles stay at least 4 s plus about 0.3 s per word, or until closed, and pause while hovered.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-08"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-09",
      "statement": "Links in speech bubbles can be clicked, through the layout's anchorAt, with only safe schemes.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-09"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-10",
      "statement": "Long answers open at the start of the newest exchange.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-10"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-11",
      "statement": "The ask box can grow to about 55% of the screen height with an expand toggle reported to its owner, and turns are separated by a rule.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-11"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-12",
      "statement": "The field takes several lines: Enter sends, Shift+Enter adds a line, and a paste keeps its line breaks.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-12"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-13",
      "statement": "Animated bubble art runs for one or two loop periods, settles on the still picture, restarts on hover or a new message, and power saving shows the still picture.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-13"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-14",
      "statement": "The animated ask box repaints only its animated ring.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-14"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-15",
      "statement": "The still picture and border are cached per size, with the notch drawn separately.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-15"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-16",
      "statement": "Each answer and each code block has a Copy action, emitted as a signal.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-16"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-17",
      "statement": "A small QSyntaxHighlighter colours keywords, strings, comments and numbers in code blocks, themed by bubble style.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-17"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-18",
      "statement": "A busy state shows the brain's name and elapsed seconds, a Stop button emits a signal, and streamed text can be shown.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-18"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-19",
      "statement": "The ask box fades in and out, unless reduced motion is on.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-19"
      ],
      "superseded_by": null
    },
    {
      "id": "R-M2-20",
      "statement": "Every style's link and selection colours reach 4.5:1 against their bubble.",
      "priority": "normal",
      "acceptance": [
        "AC-M2-20"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-M2-01",
      "requirement": "R-M2-01",
      "given": "An answer naming a real picture as a markdown image, a reference image, an HTML img and a CSS background, and titles, hints and attachment names that look like HTML",
      "when": "it is shown in a speech bubble or the ask box, including as the second text of a document already laid out and drawn",
      "then": "no resource request returns the file's bytes, Qt never reads it itself, the HTML shows as text, no image is left in, nothing of the picture is drawn, and labels and tooltips show the markup as text",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-02",
      "requirement": "R-M2-02",
      "given": "A fenced code block with lines wider than the bubble, and level-1 and level-2 headings",
      "when": "it is shown in a speech bubble and in the ask box",
      "then": "every code line wraps inside the text width on a tinted panel with padding, in a fixed-width font, and headings are at most one size step above the text",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-03",
      "requirement": "R-M2-03",
      "given": "A message taller than 40% of the screen with more buttons than fit on one row, and an on_more handler",
      "when": "it is shown",
      "then": "the bubble is at most 40% of the screen high, its text ends in an ellipsis, a More button passes the title and the whole text to on_more, and the buttons wrap onto rows inside the bubble",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-04",
      "requirement": "R-M2-04",
      "given": "A title wider than the widest bubble",
      "when": "the bubble is laid out",
      "then": "the title takes at most two lines, ending in an ellipsis, inside the bubble and clear of the close button, and the text starts below it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-05",
      "requirement": "R-M2-05",
      "given": "The plain style under a light, a dark, two Windows high contrast and a low-contrast palette, and every painted style",
      "when": "the colours are resolved",
      "then": "the plain style's come from the palette roles, changed only where a pair falls short, and every text, link, hint, field and button label pair reaches 4.5:1",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-06",
      "requirement": "R-M2-06",
      "given": "The open ask box in every style",
      "when": "each control takes the keyboard focus",
      "then": "a 2 px outline in the focus colour (3:1 against the bubble) is drawn round it, and not without the focus",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-07",
      "requirement": "R-M2-07",
      "given": "An app font larger than the bubbles' 10.5 pt, or a text-size factor",
      "when": "the speech bubble and the ask box lay out",
      "then": "their text is the larger of its own size and the app font, times the factor, and their widths grow with the font",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-08",
      "requirement": "R-M2-08",
      "given": "Messages of different lengths with a short requested timeout, and the until-closed policy",
      "when": "they are shown, hovered and left",
      "then": "each stays at least the longer of its timeout and 4 s plus 0.3 s a word (times the policy's factor), or until closed, and doesn't expire while hovered, the hovered time added back",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-09",
      "requirement": "R-M2-09",
      "given": "A speech bubble with an https link, a mailto link and a file: link",
      "when": "the pointer is over each",
      "then": "hit() says link and link_at() gives the URL for the safe ones only, and open_link_at() opens only http, https or mailto",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-10",
      "requirement": "R-M2-10",
      "given": "A chat taller than the answer area whose newest answer is long",
      "when": "it is shown at its end",
      "then": "the newest question's paragraph is at the top of the view, not the answer's last lines",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-11",
      "requirement": "R-M2-11",
      "given": "An ask box with a long chat",
      "when": "the expand toggle is pressed and pressed again",
      "then": "it grows to about 55% of the screen's height and wider, emitting expand_changed(True), then shrinks back, emitting expand_changed(False); each turn after the first is ruled off",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-12",
      "requirement": "R-M2-12",
      "given": "The ask box asking a question, and the same box naming the chatmon",
      "when": "Shift+Enter is pressed, short text with line breaks is pasted, and Enter is pressed",
      "then": "the question keeps its lines and the field grows to show them, Enter sends the whole text, and a name stays on one line",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-13",
      "requirement": "R-M2-13",
      "given": "An animated speech bubble and an animated ask box",
      "when": "they have been up past their run and settle time, are hovered, get new text, or power saving is on",
      "then": "they stop asking to be redrawn and draw the still picture, start again for hover or new text, and with power saving draw only the still",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-14",
      "requirement": "R-M2-14",
      "given": "The animated ask box, open",
      "when": "its frames run for a second",
      "then": "the box repaints, and none of its child widgets gets a paint event from the animation",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-15",
      "requirement": "R-M2-15",
      "given": "A painted bubble whose notch moves every frame",
      "when": "it is drawn with the notch at many places",
      "then": "the picture above the notch's band and the border geometry are composed once per size, and every drawing matches the picture composed whole",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-16",
      "requirement": "R-M2-16",
      "given": "The ask box showing a chat with answers and code blocks",
      "when": "a Copy link is clicked",
      "then": "copy_requested is emitted with that answer's or code block's text, and a link an answer writes to the same scheme copies nothing",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-17",
      "requirement": "R-M2-17",
      "given": "Code blocks in Python, JavaScript and an unknown language, in every style",
      "when": "they are shown",
      "then": "keywords, strings, comments and numbers are drawn in the style's code colours, each 4.5:1 against the code panel, and text outside code is not coloured",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-18",
      "requirement": "R-M2-18",
      "given": "A question being answered",
      "when": "set_busy(label, started_at) is called, time passes, Stop is pressed, partial text arrives, and set_busy(None) is called",
      "then": "the box shows the label and the whole seconds elapsed, updated each second, Stop emits stop_requested, the partial text shows under the chat, and the busy row goes away",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-19",
      "requirement": "R-M2-19",
      "given": "The ask box as a window",
      "when": "it opens and closes with reduced motion off, then on",
      "then": "it fades in, and out as a fading copy while the box itself closes at once; with reduced motion it appears and goes at once",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-20",
      "requirement": "R-M2-20",
      "given": "Every painted style, its fill measured from its art",
      "when": "its link and selection colours are checked",
      "then": "links reach 4.5:1 against the fill and selected text 4.5:1 against the selection",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-M2-01",
      "purpose": "Safe rich text: a document that loads nothing, markdown without HTML, images removed, labels and tooltips as plain text",
      "acceptance": [
        "AC-M2-01"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/richtext.py",
          "action": "create"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-01-loads",
        "E-M2-01-empty-image",
        "E-M2-01-html",
        "E-M2-01-title-markup",
        "E-M2-01-images-left"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-02",
      "purpose": "Style colours: measured fills, readable links, selections and buttons, the plain style from the palette, WCAG contrast",
      "acceptance": [
        "AC-M2-05",
        "AC-M2-20"
      ],
      "depends_on": [
        "T-M2-01"
      ],
      "changes": [
        {
          "path": "chatmon/styles.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_contrast.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-05-palette",
        "E-M2-05-readable",
        "E-M2-05-link-colour",
        "E-M2-20-fairy-link",
        "E-M2-20-selected-text"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-03",
      "purpose": "Code blocks: wrapped, tinted, fixed-width, highlighted by style; headings capped",
      "acceptance": [
        "AC-M2-02",
        "AC-M2-17"
      ],
      "depends_on": [
        "T-M2-01",
        "T-M2-02"
      ],
      "changes": [
        {
          "path": "chatmon/richtext.py",
          "action": "modify"
        },
        {
          "path": "chatmon/highlight.py",
          "action": "create"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_rich_text.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-02-no-wrap",
        "E-M2-02-no-panel",
        "E-M2-02-headings",
        "E-M2-17-keywords",
        "E-M2-17-block-comment",
        "E-M2-17-contrast"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-04",
      "purpose": "Speech bubble: height cap and More, wrapping buttons and titles, reading time and hover pause, clickable links",
      "acceptance": [
        "AC-M2-03",
        "AC-M2-04",
        "AC-M2-08",
        "AC-M2-09"
      ],
      "depends_on": [
        "T-M2-01",
        "T-M2-02"
      ],
      "changes": [
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-03-no-cap",
        "E-M2-03-one-row",
        "E-M2-04-one-line",
        "E-M2-08-fixed-clock",
        "E-M2-08-hover-ignored",
        "E-M2-09-any-scheme",
        "E-M2-09-not-a-link"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-05",
      "purpose": "Ask box field and layout: focus outlines, several-line field, newest exchange first, expand toggle and turn rules",
      "acceptance": [
        "AC-M2-06",
        "AC-M2-10",
        "AC-M2-11",
        "AC-M2-12"
      ],
      "depends_on": [
        "T-M2-01",
        "T-M2-02",
        "T-M2-03"
      ],
      "changes": [
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_ask_box.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-06-buttons",
        "E-M2-06-field",
        "E-M2-10-at-the-end",
        "E-M2-11-no-room",
        "E-M2-11-no-rules",
        "E-M2-12-no-new-line",
        "E-M2-12-paste-joined",
        "E-M2-12-qt-selection"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-06",
      "purpose": "Ask box actions: Copy, busy state with Stop and streamed text, fades",
      "acceptance": [
        "AC-M2-16",
        "AC-M2-18",
        "AC-M2-19"
      ],
      "depends_on": [
        "T-M2-05"
      ],
      "changes": [
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_ask_box.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-16-no-copy",
        "E-M2-16-forged",
        "E-M2-18-no-clock",
        "E-M2-18-no-stop",
        "E-M2-18-no-partial",
        "E-M2-19-no-fade-in",
        "E-M2-19-no-ghost",
        "E-M2-19-motion-ignored"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-07",
      "purpose": "Text size: the app font and a text-size factor, widths from font metrics",
      "acceptance": [
        "AC-M2-07"
      ],
      "depends_on": [
        "T-M2-04",
        "T-M2-05"
      ],
      "changes": [
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_ask_box.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-07-desktop-font",
        "E-M2-07-fixed-width",
        "E-M2-07-box-width"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M2-08",
      "purpose": "Drawing cost: effects settle, the ask box repaints its ring only, art cached per size with the notch apart",
      "acceptance": [
        "AC-M2-13",
        "AC-M2-14",
        "AC-M2-15"
      ],
      "depends_on": [
        "T-M2-04",
        "T-M2-05"
      ],
      "changes": [
        {
          "path": "chatmon/bubbleart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-M2-behavior-1",
        "E-M2-13-never-settles",
        "E-M2-13-power-saving",
        "E-M2-13-hover-wake",
        "E-M2-13-box-keeps-drawing",
        "E-M2-14-whole-box",
        "E-M2-15-upper-every-time",
        "E-M2-15-border-per-notch",
        "E-M2-15-band-off-by-one"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-M2-readiness-1",
      "acceptance": [
        "AC-M2-01",
        "AC-M2-02",
        "AC-M2-03",
        "AC-M2-04",
        "AC-M2-05",
        "AC-M2-06",
        "AC-M2-07",
        "AC-M2-08",
        "AC-M2-09",
        "AC-M2-10",
        "AC-M2-11",
        "AC-M2-12",
        "AC-M2-13",
        "AC-M2-14",
        "AC-M2-15",
        "AC-M2-16",
        "AC-M2-17",
        "AC-M2-18",
        "AC-M2-19",
        "AC-M2-20"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review: each item re-checked in the code at 5346385 and by probes (M2-01 file read reproduced), conflicts with the roadmap contract and callers resolved, failure behavior specified, coverage and ordering checked; recorded in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m2/readiness.md",
        "sha256": "e1324485b136875bc99b1cee0e424cb97ef3784b431e5c8548023f92f3b782ed"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "d5659c6eb4e43012cbbc03ff40f00adc25a74a1a15a6b3972de59048a0affcde",
      "red": null,
      "reason": "The plan's narrative changed at closure (budgets restated, notes filled in); re-reviewed in E-M2-readiness-2."
    },
    {
      "id": "E-M2-readiness-2",
      "acceptance": [
        "AC-M2-01",
        "AC-M2-02",
        "AC-M2-03",
        "AC-M2-04",
        "AC-M2-05",
        "AC-M2-06",
        "AC-M2-07",
        "AC-M2-08",
        "AC-M2-09",
        "AC-M2-10",
        "AC-M2-11",
        "AC-M2-12",
        "AC-M2-13",
        "AC-M2-14",
        "AC-M2-15",
        "AC-M2-16",
        "AC-M2-17",
        "AC-M2-18",
        "AC-M2-19",
        "AC-M2-20"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Closure re-review of the requirements and the changed narrative against the brief and rules; recorded in the artifact's closure section.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m2/readiness.md",
        "sha256": "c34ddbd4c14eda65497e3e1bc184fe0f90dc52034e465f038d943705efdae86d"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "4b09f3eca78c53004a2ca428ad91523f0634d7e88208569e00eafa793a648f31",
      "red": null,
      "reason": null
    },
    {
      "id": "E-M2-behavior-1",
      "acceptance": [
        "AC-M2-01",
        "AC-M2-02",
        "AC-M2-03",
        "AC-M2-04",
        "AC-M2-05",
        "AC-M2-06",
        "AC-M2-07",
        "AC-M2-08",
        "AC-M2-09",
        "AC-M2-10",
        "AC-M2-11",
        "AC-M2-12",
        "AC-M2-13",
        "AC-M2-14",
        "AC-M2-15",
        "AC-M2-16",
        "AC-M2-17",
        "AC-M2-18",
        "AC-M2-19",
        "AC-M2-20"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on the final source (the tests for every M2 item among them: test_bubble_safety, test_contrast, test_rich_text, test_speech_bubble, test_ask_box, test_bubble_styles), offscreen; the log's summary line is the result.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/final-pytest.log",
        "sha256": "9d209da6366dc289bc58430222c22c01b16c00d292b582d765977846bc032d66"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "4b09f3eca78c53004a2ca428ad91523f0634d7e88208569e00eafa793a648f31",
      "red": null,
      "reason": null
    },
    {
      "id": "E-M2-01-loads",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-01-loads in a temporary copy (tests/drills/run.py): tests/test_bubble_safety.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        }
      ],
      "scope_sha256": "944d7853dfd1e4ecf548767f563d926dbfc9fecbd7da746ed0b154aa4cf20bd7",
      "red": {
        "mutation": "chatmon/richtext.py: replace '        return nothing(kind)' with '        return super().loadResource(kind, url)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "a picture's bytes were read",
        "observed_diagnostic": ">       assert leaked == [], f\"a picture's bytes were read for {leaked}\"",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "ace90263b2fa7a7fbece6e20921ef1696c804bfcdb65762ad80405425bbaa782"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-01-empty-image",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-01-empty-image in a temporary copy (tests/drills/run.py): tests/test_bubble_safety.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        }
      ],
      "scope_sha256": "944d7853dfd1e4ecf548767f563d926dbfc9fecbd7da746ed0b154aa4cf20bd7",
      "red": {
        "mutation": "chatmon/richtext.py: replace '        return blank' with '        return b\"\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "itself",
        "observed_diagnostic": "# Qt keeps a picture it read itself (when a request came back empty) as the document's resource. (Asking",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "9f8cec4190a243f36e2bf818a6b4330566e880ecc2315552e786b8579ee7affe"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-01-html",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-01-html in a temporary copy (tests/drills/run.py): tests/test_bubble_safety.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        }
      ],
      "scope_sha256": "944d7853dfd1e4ecf548767f563d926dbfc9fecbd7da746ed0b154aa4cf20bd7",
      "red": {
        "mutation": "chatmon/richtext.py: replace 'MARKDOWN = QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML' with 'MARKDOWN = QTextDocument.MarkdownFeature.MarkdownDialectGitHub'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "HTML was read",
        "observed_diagnostic": ">       assert '<img src=\"' in shown and \"background-image\" in shown, \"HTML was read: it doesn't show as the text it is\"",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "41438f7a89ac7ce1691331a4d859812b714399590bdbb294c7ed177aaf3bb742"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-01-images-left-attempt-1",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "fail",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-01-images-left in the full drill run.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 1,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [],
      "scope_sha256": null,
      "red": null,
      "reason": "mutation text occurs 0 times, expected 1: its two-line find text had LF endings and the file has CRLF. Re-run with a one-line find as E-M2-01-images-left (drills-rerun.log)."
    },
    {
      "id": "E-M2-01-title-markup",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-01-title-markup in a temporary copy (tests/drills/run.py): tests/test_bubble_safety.py::test_a_title_hint_or_attachment_name_is_shown_as_text green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        }
      ],
      "scope_sha256": "944d7853dfd1e4ecf548767f563d926dbfc9fecbd7da746ed0b154aa4cf20bd7",
      "red": {
        "mutation": "chatmon/bubble.py: replace 'self.title.setTextFormat(Qt.TextFormat.PlainText)' with 'self.title.setTextFormat(Qt.TextFormat.AutoText)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "magenta_pixels",
        "observed_diagnostic": ">           assert magenta_pixels(box.grab().toImage()) == 0",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "656049b9809989656c4ce0a3e8a2e55c280ce1cf32e0a98ce9c43cd34095c461"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-05-palette",
      "acceptance": [
        "AC-M2-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-05-palette in a temporary copy (tests/drills/run.py): tests/test_contrast.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        }
      ],
      "scope_sha256": "ae3270f4cfac98f22f1c47347264c2cbd1873d530ab472d50b71e27367dac727",
      "red": {
        "mutation": "chatmon/styles.py: replace '    highlight = readable(role(QPalette.ColorRole.Highlight), fill, OUTLINE_CONTRAST)' with '    highlight = readable(QColor(PLAIN_ACCENT), fill, OUTLINE_CONTRAST)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_plain_style_wears_a_high_contrast_theme_as_it_is",
        "observed_diagnostic": "_ test_the_plain_style_wears_a_high_contrast_theme_as_it_is[windows high contrast black] _",
        "before": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/styles.py",
            "sha256": "38a140a66d70f97a2e7b1754bd69c51db29881b142ff097fb8f0dc925f95052c"
          }
        ],
        "after": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-05-readable",
      "acceptance": [
        "AC-M2-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-05-readable in a temporary copy (tests/drills/run.py): tests/test_contrast.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        }
      ],
      "scope_sha256": "ae3270f4cfac98f22f1c47347264c2cbd1873d530ab472d50b71e27367dac727",
      "red": {
        "mutation": "chatmon/styles.py: replace '    if contrast(fg, bg) >= ratio:' with '    if True:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_plain_style_reads_whatever_the_palette[faint]",
        "observed_diagnostic": "___________ test_the_plain_style_reads_whatever_the_palette[faint] ____________",
        "before": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/styles.py",
            "sha256": "993d48bdf0e5ebe856a6947e862842f0e4ed83e351905f4b91817ee9ec7d456f"
          }
        ],
        "after": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-05-link-colour",
      "acceptance": [
        "AC-M2-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-05-link-colour in a temporary copy (tests/drills/run.py): tests/test_contrast.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        }
      ],
      "scope_sha256": "ae3270f4cfac98f22f1c47347264c2cbd1873d530ab472d50b71e27367dac727",
      "red": {
        "mutation": "chatmon/richtext.py: replace '    _merge(doc, _spans(doc, lambda b, f: f.isAnchor()), look)' with '    pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_links_in_answers_wear_the_styles_colour_not_the_apps",
        "observed_diagnostic": "_____ test_links_in_answers_wear_the_styles_colour_not_the_apps[electric] _____",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "14a829f366158c8983f18ce199c73e3be912507502e79d2413af39928e9b8bff"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-20-fairy-link",
      "acceptance": [
        "AC-M2-20"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-20-fairy-link in a temporary copy (tests/drills/run.py): tests/test_contrast.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        }
      ],
      "scope_sha256": "ae3270f4cfac98f22f1c47347264c2cbd1873d530ab472d50b71e27367dac727",
      "red": {
        "mutation": "chatmon/styles.py: replace 'fill=\"#fad7e3\", link=\"#9c2f5b\"' with 'fill=\"#fad7e3\", link=\"#d4658f\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "fairy links",
        "observed_diagnostic": "E       AssertionError: fairy links: 2.62",
        "before": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/styles.py",
            "sha256": "5167300409dbf78b783035976585bfbed0d1cc7ecebadcdd294a421b14d48ea4"
          }
        ],
        "after": [
          {
            "path": "chatmon/styles.py",
            "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-20-selected-text",
      "acceptance": [
        "AC-M2-20"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-20-selected-text in a temporary copy (tests/drills/run.py): tests/test_contrast.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        }
      ],
      "scope_sha256": "ae3270f4cfac98f22f1c47347264c2cbd1873d530ab472d50b71e27367dac727",
      "red": {
        "mutation": "chatmon/bubble.py: replace ' selection-color: {c.selection_text.name()};' with ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_selected_text_in_the_ask_box_wears_the_selection_colours",
        "observed_diagnostic": "___ test_selected_text_in_the_ask_box_wears_the_selection_colours[electric] ___",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "481d70b7e2a79585556814f888c34573a985f3442fbd1d78475cd46f62a5464e"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-02-no-wrap",
      "acceptance": [
        "AC-M2-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-02-no-wrap in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/richtext.py: replace '    code.setNonBreakableLines(False)' with '    code.setNonBreakableLines(True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_code_wraps_on_a_tinted_panel_in_a_speech_bubble",
        "observed_diagnostic": "_______ test_code_wraps_on_a_tinted_panel_in_a_speech_bubble[electric] ________",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "7a256747a90130c32136ead1422d23d5a7db1733b76f25647cb6705e6002f6e7"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-02-no-panel",
      "acceptance": [
        "AC-M2-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-02-no-panel in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/richtext.py: replace '    panel.setBackground(look.code_fill)' with '    pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_code_wraps_on_a_tinted_panel_in_a_speech_bubble",
        "observed_diagnostic": "_______ test_code_wraps_on_a_tinted_panel_in_a_speech_bubble[electric] ________",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "7f1f45786c36529a6b34376607bb29410293ae1ec80a0cccc95b0fcc45f7348e"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-02-headings",
      "acceptance": [
        "AC-M2-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-02-headings in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/richtext.py: replace 'HEADING_MOST = 1  #' with 'HEADING_MOST = 3  #'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_headings_stay_near_the_texts_size",
        "observed_diagnostic": "___________________ test_headings_stay_near_the_texts_size ____________________",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "dfdfc548108c51ad35d9591d1a27257aa31f3f81bc95728b95f02d449fb58e39"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-17-keywords",
      "acceptance": [
        "AC-M2-17"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-17-keywords in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/highlight.py: replace '                if word.group() in keywords:' with '                if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_python_keywords_strings_numbers_and_comments_are_coloured",
        "observed_diagnostic": "_______ test_python_keywords_strings_numbers_and_comments_are_coloured ________",
        "before": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "902845f114cc51377e4bbb9cdbf7d5bbb68302ba8b3a7b2f2ba1aa817ed29d75"
          }
        ],
        "after": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-17-block-comment",
      "acceptance": [
        "AC-M2-17"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-17-block-comment in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/highlight.py: replace 'self.setCurrentBlockState(INSIDE_COMMENT)' with 'self.setCurrentBlockState(0)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_block_comment_carries_on_to_the_next_lines",
        "observed_diagnostic": "______________ test_a_block_comment_carries_on_to_the_next_lines ______________",
        "before": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "0ea07770608d6d67c2ae99bb0ff37e2e2acfd2e3784d2195c0504756090f753a"
          }
        ],
        "after": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-17-contrast",
      "acceptance": [
        "AC-M2-17"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-17-contrast in a temporary copy (tests/drills/run.py): tests/test_rich_text.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "6a79fd066799b2f488afca24e8ce3220ea605800cadbebfd2e12ec955ad43f89",
      "red": {
        "mutation": "chatmon/highlight.py: replace 'styles.readable(styles.blend(c.body, panel, 150), panel))' with 'styles.blend(c.body, panel, 60))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_code_colours_read_on_the_code_panel_and_stand_apart",
        "observed_diagnostic": "_____ test_code_colours_read_on_the_code_panel_and_stand_apart[electric] ______",
        "before": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "7b9e47ac66d3cac17c391018f276e7ec09271f31f41ec5e435fec7fd682ee281"
          }
        ],
        "after": [
          {
            "path": "chatmon/highlight.py",
            "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-03-no-cap",
      "acceptance": [
        "AC-M2-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-03-no-cap in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        if has_text and 6 + text_h + (12 + rows_h if buttons else 0) > room:' with '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_long_message_is_capped_and_more_has_the_rest",
        "observed_diagnostic": "________ test_a_long_message_is_capped_and_more_has_the_rest[electric] ________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "26e066e015201d47ceafb56c6670dc7b3440536d6d0a17a6b8ecd30c419551ef"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-03-one-row",
      "acceptance": [
        "AC-M2-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-03-one-row in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            if rows[-1] and used + self.BUTTON_GAP + b.rect.width() > inner:' with '            if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_buttons_wrap_onto_rows_inside_the_bubble",
        "observed_diagnostic": "___________ test_buttons_wrap_onto_rows_inside_the_bubble[electric] ___________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "cd3127400d5a51e2f9dcef0cf5a0b86b628f31ea55946f34ae1b92f47c4e911b"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-04-one-line",
      "acceptance": [
        "AC-M2-04"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-04-one-line in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        self._title_lines = text_lines(self.title, title_font, inner - self.CLOSE_W, self.TITLE_LINES)' with '        self._title_lines = [self.title]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_long_title_stays_inside_the_bubble_and_clear_of_the_close_button",
        "observed_diagnostic": "_ test_a_long_title_stays_inside_the_bubble_and_clear_of_the_close_button[electric] _",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "17b40173554fb8abf52b8763f756c05812a916ca9051932c8dd80e11e708ea37"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-08-fixed-clock",
      "acceptance": [
        "AC-M2-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-08-fixed-clock in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return max(asked, self.least + self.per_word * words) * max(0.25, self.factor)' with '        return asked * max(0.25, self.factor)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bubble_stays_long_enough_to_read",
        "observed_diagnostic": "___________________ test_a_bubble_stays_long_enough_to_read ___________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "5efc81cb3b33ecfdb922c9ed0e9e1056ce83d92d72ee24d5cf33c1b64d164fc1"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-08-hover-ignored",
      "acceptance": [
        "AC-M2-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-08-hover-ignored in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        if self._expires is not None and not self._hovered and now >= self._expires:' with '        if self._expires is not None and now >= self._expires:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_hovered_bubble_waits_and_then_goes_on_from_where_it_was",
        "observed_diagnostic": "_______ test_a_hovered_bubble_waits_and_then_goes_on_from_where_it_was ________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "1206282d26c7f3a9eee726858ac93f63f74f59150ac55b1c6b653cfaf2ce12f9"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-09-any-scheme",
      "acceptance": [
        "AC-M2-09"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-09-any-scheme in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return url if url is not None and url.scheme() in SAFE_SCHEMES else None' with '        return url'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_links_in_a_bubble_can_be_clicked_but_only_safe_ones",
        "observed_diagnostic": "__________ test_links_in_a_bubble_can_be_clicked_but_only_safe_ones ___________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "b15a8c94b175151b7d197ca3ee959aaed939591434438cbd6f7a577895a32d0d"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-09-not-a-link",
      "acceptance": [
        "AC-M2-09"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-09-not-a-link in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "b3d3a3dfbe0a0fd9dffd2e228b37081612013588698ea7e1221f7208b128b31f",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            return \"link\"' with '            return \"body\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_links_in_a_bubble_can_be_clicked_but_only_safe_ones",
        "observed_diagnostic": "__________ test_links_in_a_bubble_can_be_clicked_but_only_safe_ones ___________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "21c71bd341d62b04a50d6bd94f338f5d5b2ba87a9cdffe6c5433a091754fd914"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-07-desktop-font",
      "acceptance": [
        "AC-M2-07"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-07-desktop-font in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "9519c0f3055602d275fd95745ed0d2a3a92d67fe63e32e48a439043e25b401d5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '    grow = desktop / BODY_POINTS if desktop > BODY_POINTS else 1.0' with '    grow = 1.0'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_text_follows_a_larger_desktop_font",
        "observed_diagnostic": "___________________ test_text_follows_a_larger_desktop_font ___________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "bd53c6d65cc83e8d1d5cdd14d53edfa98fd62836ea3f5582954ded95ec0f8b28"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-07-fixed-width",
      "acceptance": [
        "AC-M2-07"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-07-fixed-width in a temporary copy (tests/drills/run.py): tests/test_speech_bubble.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "9519c0f3055602d275fd95745ed0d2a3a92d67fe63e32e48a439043e25b401d5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return min(room, width_for(self.MAX_WIDTH, body))' with '        return min(room, self.MAX_WIDTH)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_text_size_setting_scales_text_and_widths",
        "observed_diagnostic": "______________ test_the_text_size_setting_scales_text_and_widths ______________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "28faf266c0afa8ad46c6d04d513a9b26eb5697b9ed8c7f37d9b9e5c045b3d737"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-06-buttons",
      "acceptance": [
        "AC-M2-06"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-06-buttons in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            QToolButton:focus {{ border: 2px solid {focus}; }}' with ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "shows its focus",
        "observed_diagnostic": ">           assert ring(box, control, focus) == 4, f\"{what} shows its focus ({name})\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "5cdb6e203f384e879e835d78707d109f0fd27a4c9a66f2e1539336d865280405"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-06-field",
      "acceptance": [
        "AC-M2-06"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-06-field in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace 'QTextEdit#entry:focus {{ border: 2px solid {focus}; padding: 3px 5px; }}' with 'QTextEdit#entry:focus {{ border: 1px solid {focus}; padding: 4px 6px; }}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "field shows its focus",
        "observed_diagnostic": "E           AssertionError: field shows its focus (electric)",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "e470823612c60fa5061625274eb46b41f4abffad972db3a9418b7e810ff3ba2c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-07-box-width",
      "acceptance": [
        "AC-M2-07"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-07-box-width in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "9519c0f3055602d275fd95745ed0d2a3a92d67fe63e32e48a439043e25b401d5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        width = width_for(self.WIDTH, self._body_font()) * (self.EXPANDED_WIDTH if self.expanded else 1.0)' with '        width = self.WIDTH * (self.EXPANDED_WIDTH if self.expanded else 1.0)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_text_size_setting_grows_the_box_and_its_text",
        "observed_diagnostic": "____________ test_the_text_size_setting_grows_the_box_and_its_text ____________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "00cb55195eca8c36f414573d73cc4d4a8411ce29215567264d8fbae6e208957c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-10-at-the-end",
      "acceptance": [
        "AC-M2-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-10-at-the-end in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            bar.setValue(min(bar.maximum(), int(top)))' with '            bar.setValue(bar.maximum())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_long_answer_opens_at_the_start_of_the_newest_exchange",
        "observed_diagnostic": "________ test_a_long_answer_opens_at_the_start_of_the_newest_exchange _________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f48502e7e9c5c55f877846085fc1171498b6e6476b0b0bf6342193db41077e7"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-11-no-room",
      "acceptance": [
        "AC-M2-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-11-no-room in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return room if self.expanded else min(' with '        return min('",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_box_can_be_made_bigger_and_back",
        "observed_diagnostic": "__________________ test_the_box_can_be_made_bigger_and_back ___________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "03f0783c0fa1bf70ef6698b8186df6fe56d3cfb8d5beed5abd6edcb33ed2cf00"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-11-no-rules",
      "acceptance": [
        "AC-M2-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-11-no-rules in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/richtext.py: replace '        inserts.append((start - 1, \"rule\", None))' with '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_turns_are_ruled_apart",
        "observed_diagnostic": "_________________________ test_turns_are_ruled_apart __________________________",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "0420862060ca6ef914d7f09119fd47b106a18b166211732902dcee84fc99bcf4"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-12-no-new-line",
      "acceptance": [
        "AC-M2-12"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-12-no-new-line in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            if self.multiline and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:' with '            if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_shift_enter_adds_a_line_and_enter_sends_it_all",
        "observed_diagnostic": "_____________ test_shift_enter_adds_a_line_and_enter_sends_it_all _____________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9b64310c3e3d4ca55b0dacaec93d1ae6bb0990d8091071c87fb9ce19d01ffae0"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-12-paste-joined",
      "acceptance": [
        "AC-M2-12"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-12-paste-joined in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return text if self.multiline else \" \".join(text.splitlines())' with '        return \" \".join(text.splitlines())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_short_paste_keeps_its_line_breaks",
        "observed_diagnostic": "__________________ test_a_short_paste_keeps_its_line_breaks ___________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "30fa01879b50c199077626304b733f4c5152acadae386cc7ccb87bacdd47a1ce"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-12-qt-selection",
      "acceptance": [
        "AC-M2-12"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-12-qt-selection in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "242cc285d021675cda7bc16fca6e56671987c031d652b93f4f1e5cc94ea9cb4e",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        if query == Qt.InputMethodQuery.ImCurrentSelection:' with '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_field_keeps_the_calls_the_app_and_overlay_use",
        "observed_diagnostic": "___________ test_the_field_keeps_the_calls_the_app_and_overlay_use ____________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "4194c108a643128c1be87dda69aba602cf9a25265a0ceafc3e659fe9383d4cd4"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-16-no-copy",
      "acceptance": [
        "AC-M2-16"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-16-no-copy in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            self.copy_requested.emit(texts[n])' with '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_answer_and_code_block_can_be_copied",
        "observed_diagnostic": "________________ test_each_answer_and_code_block_can_be_copied ________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "142f2763ade2b01799f239309be840c27a30845d27d282a7fd2e773e6d7324bc"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-16-forged",
      "acceptance": [
        "AC-M2-16"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-16-forged in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/richtext.py: replace '    return int(n) if given == token and n.isdigit() else None' with '    return int(n) if n.isdigit() else None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_copy_link_written_by_an_answer_copies_nothing",
        "observed_diagnostic": "____________ test_a_copy_link_written_by_an_answer_copies_nothing _____________",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "4da656e9390042897289bd810b6d86f49365c3141f131058dc6002fe0bb75a55"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-18-no-clock",
      "acceptance": [
        "AC-M2-18"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-18-no-clock in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '                self._busy_clock.start()' with '                pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "it counts each second",
        "observed_diagnostic": ">       assert box.busy_label.text() == \"Claude is answering… 13 s\", \"it counts each second\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "e38e214c2db4be09815c98d4dfa21f1ca6f0e4eb66f521fa307a351d2119f08f"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-18-no-stop",
      "acceptance": [
        "AC-M2-18"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-18-no-stop in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        self.stop_button.clicked.connect(self.stop_requested.emit)' with '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_answer_on_its_way_shows_who_and_how_long_and_can_be_stopped",
        "observed_diagnostic": "_____ test_an_answer_on_its_way_shows_who_and_how_long_and_can_be_stopped _____",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "604d5e8c0b896cbf82ce873afa07a83e80cb70a8884d053ec7623f63bb39a848"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-18-no-partial",
      "acceptance": [
        "AC-M2-18"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-18-no-partial in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        self._partial += text' with '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_streamed_text_shows_as_it_comes_and_the_answer_replaces_it",
        "observed_diagnostic": "_______ test_streamed_text_shows_as_it_comes_and_the_answer_replaces_it _______",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "c5efc30d5a2585fa5a9b05131e4aea86df6f2644b96276449a0e7b07340b31d8"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-19-no-fade-in",
      "acceptance": [
        "AC-M2-19"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-19-no-fade-in in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            self._fade_in.start()' with '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_fades_in_and_out",
        "observed_diagnostic": "__________________________ test_it_fades_in_and_out ___________________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "0450c9a35834e725058a2480fd29c336a6a3bc8ac81719c06790622a106c002c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-19-no-ghost",
      "acceptance": [
        "AC-M2-19"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-19-no-ghost in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '                _Ghost(self.grab(), self.geometry(), self.windowOpacity(), self.FADE_MS)' with '                pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_fades_in_and_out",
        "observed_diagnostic": "__________________________ test_it_fades_in_and_out ___________________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "c2dd345056ceac64a8e7f518e90ac0fb0e325c1a56fa0ab5d9c4a14e2791dd7f"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-19-motion-ignored",
      "acceptance": [
        "AC-M2-19"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-19-motion-ignored in a temporary copy (tests/drills/run.py): tests/test_ask_box.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        }
      ],
      "scope_sha256": "571a47f0ea73e8b8d1d17a36f0e713995cc803b77e9754741d0f1d06ec8a09e7",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return not self.reduced_motion and not self.stage_draws_art' with '        return not self.stage_draws_art'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_with_reduced_motion_it_comes_and_goes_at_once",
        "observed_diagnostic": "_____________ test_with_reduced_motion_it_comes_and_goes_at_once ______________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "4948d4287e89090944ea3659ac8df6f5313a11c286d8d694e98cb37ad7e7ffea"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-13-never-settles",
      "acceptance": [
        "AC-M2-13"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-13-never-settles in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        return min(rise, 1 - _smooth((age - run) / EFFECTS_SETTLE))' with '        return rise'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_speech_bubbles_effects_settle_and_come_back",
        "observed_diagnostic": "________ test_a_speech_bubbles_effects_settle_and_come_back[electric] _________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "5a14de2ff1b30bf0e42b87cc50d8ac5e63f497391b13d067b4106353826e94a0"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-13-power-saving",
      "acceptance": [
        "AC-M2-13"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-13-power-saving in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        if not (self._visible and self.animate and self.art is not None and self.art.layers) or self.power_saving:' with '        if not (self._visible and self.animate and self.art is not None and self.art.layers):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "power saving: the still picture",
        "observed_diagnostic": ">       assert message.anim_key(end + 100.6) == -1, \"power saving: the still picture\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9775306838fa0b445bb734625ef7b96555beef712bdc5ff8548d997f77f56b22"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-13-hover-wake",
      "acceptance": [
        "AC-M2-13"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-13-hover-wake in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            self._effects.wake(now, self._period)' with '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "pointed at, it moves again",
        "observed_diagnostic": ">       assert message.anim_key(end + 1.1) != -1, \"pointed at, it moves again\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "5dabd324a91ae0bb3799c76f98c2c0e5a225dba8aa520effd5ec2d67fc8e933c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-13-box-keeps-drawing",
      "acceptance": [
        "AC-M2-13"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-13-box-keeps-drawing in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '            self._frames.stop()  # that was the still picture: nothing more to draw' with '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_ask_box_settles_and_wakes",
        "observed_diagnostic": "_____________________ test_the_ask_box_settles_and_wakes ______________________",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9e818957d64c6c42bd89d8a02eaa7b3f6d40f8d4a79b1c88b41c9934a2bdbdd3"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-14-whole-box",
      "acceptance": [
        "AC-M2-14"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-14-whole-box in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubble.py: replace '        self.update(self._ring())' with '        self.update()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "nothing inside it is drawn again",
        "observed_diagnostic": ">       assert paints.children == 0, \"nothing inside it is drawn again\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "c222384335e0bca80fbeaac703090d771f4ffeed024887501dab614f4d3246e9"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-15-upper-every-time",
      "acceptance": [
        "AC-M2-15"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-15-upper-every-time in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubbleart.py: replace '        upper = self._cache.get((tag, tw, th, ratio))' with '        upper = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "is composed once per size",
        "observed_diagnostic": ">       assert uppers <= 2, f\"{name}: the picture above the band is composed once per size and art ({uppers} times)\"",
        "before": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "12438eca8c425ac2ac0382456736a4464ed92637138d02df78871b4ce198a92c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-15-border-per-notch",
      "acceptance": [
        "AC-M2-15"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-15-border-per-notch in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubbleart.py: replace '        if key not in self._rims:' with '        if True:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "one border for the size",
        "observed_diagnostic": ">       assert len(rims) == 1, \"one border for the size, whatever the notch\"",
        "before": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "fe58ab3af968db83f9e7b4d66cf9f697dcc92b7d70debbd765bda142d417d50d"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-15-band-off-by-one",
      "acceptance": [
        "AC-M2-15"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--log",
        "docs/delivery/reports/m2/drills.log"
      ],
      "method": "Red drill M2-15-band-off-by-one in a temporary copy (tests/drills/run.py): tests/test_bubble_styles.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills.log",
        "sha256": "e8b68e2d2909a6495311fe2cd4010b16ae9550a334ab2aca51171c82fbdcd5aa"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
        },
        {
          "path": "chatmon/highlight.py",
          "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_ask_box.py",
          "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
        },
        {
          "path": "tests/test_speech_bubble.py",
          "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
        }
      ],
      "scope_sha256": "213f9891adc90d8b3b2523dbaaaf40a2970830849fe4db4f4b5d71716c6251b5",
      "red": {
        "mutation": "chatmon/bubbleart.py: replace '        p.translate(0, -first / ratio)' with '        p.translate(0, -first / ratio + 1)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_still_kept_in_two_parts_is_the_whole_picture_wherever_the_notch_is",
        "observed_diagnostic": "_ test_the_still_kept_in_two_parts_is_the_whole_picture_wherever_the_notch_is[1.0-electric] _",
        "before": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "0154044f92ce6ebf705037773af91c6fb6a4c1531fb2363d1b8128242926dccb"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubbleart.py",
            "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-M2-01-images-left",
      "acceptance": [
        "AC-M2-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m2/drill-spec.json",
        "--only",
        "M2-01-images-left",
        "--log",
        "docs/delivery/reports/m2/drills-rerun.log"
      ],
      "method": "Red drill M2-01-images-left in a temporary copy (tests/drills/run.py): tests/test_bubble_safety.py green, red with the mutation, green again after the file's bytes were restored and checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m2/drills-rerun.log",
        "sha256": "a512c807e0682dfb550e4900e8a750dde933816ef9bde8a6693ce905bd8045ee"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_bubble_safety.py",
          "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
        }
      ],
      "scope_sha256": "944d7853dfd1e4ecf548767f563d926dbfc9fecbd7da746ed0b154aa4cf20bd7",
      "red": {
        "mutation": "chatmon/richtext.py: replace '    without_images(doc)' with '    pass  # the images left in'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "an image was left in",
        "observed_diagnostic": ">       assert images(doc) == 0, \"an image was left in, for the screen to look for its @2x file\"",
        "before": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "825a938644e940aa0ac3eebcc151f066cec179d537fb281a0986c87035a487e0"
          }
        ],
        "after": [
          {
            "path": "chatmon/richtext.py",
            "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "4b09f3eca78c53004a2ca428ad91523f0634d7e88208569e00eafa793a648f31",
    "inputs": [
      {
        "path": "chatmon/bubble.py",
        "sha256": "9f49a4d5e904ea1925e83a04760796bd72db3648e9517f3421f15c6d58434f5d"
      },
      {
        "path": "chatmon/bubbleart.py",
        "sha256": "4ece0253a73e265baf7014a74d35fe94ff113f0439810f5c9a2faef211955820"
      },
      {
        "path": "chatmon/highlight.py",
        "sha256": "2cc084d73950a9080b53b9c57eba574bf0b5fcc64f28950da08d2e6b099bf7d8"
      },
      {
        "path": "chatmon/richtext.py",
        "sha256": "69381d2fd8e1ec79ad9db1e625806637110733e549b949c80b7fcd3011f0a99a"
      },
      {
        "path": "chatmon/styles.py",
        "sha256": "b9d542c9a7a97ac6a7d289faa4a3b925b73e15b8f7976da4f91911435a37dd39"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
      },
      {
        "path": "pyproject.toml",
        "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
      },
      {
        "path": "tests/test_ask_box.py",
        "sha256": "5dc85feb87a480416ae862efa0097bd34a58467dd0d8b12f396b14be86fda378"
      },
      {
        "path": "tests/test_bubble_safety.py",
        "sha256": "516fef41634baa014346436089c42f55804fc7df697cc3ae13e75234929865d0"
      },
      {
        "path": "tests/test_bubble_styles.py",
        "sha256": "93456bb4b09bc203f5e483a69533e4442ec1fea517116f293b62fb985eedec12"
      },
      {
        "path": "tests/test_contrast.py",
        "sha256": "7f51cc9eaea2e17f864f9d39849d97f99d104ff221e014d441ba8ddc35d69df4"
      },
      {
        "path": "tests/test_rich_text.py",
        "sha256": "5338f345e97b1fa7057df0712106f240200d8bc961ab4cedac0f26df4cf7c2cc"
      },
      {
        "path": "tests/test_speech_bubble.py",
        "sha256": "dd3028b4fe09e836a6291154b919ee6b9c622ff1f7ffc46741cc7de329595f91"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    },
    "verified_tasks": [
      "T-M2-01",
      "T-M2-02",
      "T-M2-03",
      "T-M2-04",
      "T-M2-05",
      "T-M2-06",
      "T-M2-07",
      "T-M2-08"
    ],
    "pending_operations": [
      {
        "id": "P-M2-ci",
        "description": "The new tests (and the cocoa and Linux paths they touch) have run on Windows only; CI runs them on Linux and macOS after the coordinator merges and pushes.",
        "next_action": "Read the CI results for wave1/m2's merge on Linux and macOS; fix any failure in M2's files and re-run this plan's checks."
      }
    ],
    "next_action": "Coordinator merges wave1/m2; M7 wires the Integration notes.",
    "source_revision": "52b35414b5ea61034c643f83291856368da41a7c"
  }
}
```
