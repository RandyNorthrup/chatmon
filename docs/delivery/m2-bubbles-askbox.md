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
- The entry field becomes a `QTextEdit` subclass that keeps `QLineEdit`'s calls the app and the overlay use
  (`text`, `setText`, `insert`, `selectAll`, `clear`, `end`, `returnPressed`, `hasSelectedText`, `selectedText`,
  `paste_requested`), so `app.py` and `penguin.py` need no change for it.
- The art cache in `bubbleart.py` is split, not replaced: the composed picture is cached per size with the
  notch's band composed separately per notch place; the border's geometry (`Rim`) is cached per size.
- Code highlighting is a `QSyntaxHighlighter` (in Qt already) in new `highlight.py`: formats are drawn, not stored,
  so copying, `toPlainText` and `toMarkdown` are unchanged.

**Contract deviation (recorded for M7).** The roadmap lists `more_requested` on the ask box. The More button the
assessment asks for (M2-03) is on the speech bubble, which has no signals (the stage draws it); it is delivered as
the callback `SpeechBubble.on_more(title, markdown)`, in the style of its existing `on_close`. The ask box has no
`more_requested`.

**Performance budgets** (this machine, offscreen, measured by [perf_bubbles.py](reports/m2/perf_bubbles.py);
relative to the "before" numbers in [perf-before.log](reports/m2/perf-before.log)): a speech bubble left up 30 s
draws at most one loop period plus the settle fade of animated frames, not 892; the animated ask box repaints
none of its child widgets per frame (170 a second before); a bubble whose notch moves every frame costs within
1.5× of one whose notch is still (3–11× before).

## Acceptance overview

Each requirement below is one assessment item, with its acceptance in the ledger. Every criterion is checked by
automated tests (behavior) and at least one red drill in [drills.json](reports/m2/drills.json).

## Integration notes

Filled in at closure.

## Changelog notes

Filled in at closure.

## README notes

Filled in at closure.

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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```
