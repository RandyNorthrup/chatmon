# The chat bubbles' art

Five painted chat bubbles, one per companion element, plus the plain bubble in the desktop's own colours. The owner
picked each design from three mock-ups (a whole bubble with its title, text and buttons, on dark and light
desktops). Made with the Codex CLI's built-in image generation (the owner's ChatGPT sign-in), one image per run.

## How it works

- **The bubble never moves.** Each style is one painted bubble with its notch as part of the same piece
  (`../../chatmon/bubbles/<style>-still.png`). `../../chatmon/bubbleart.py` draws it round
  any text as a 9-slice: the corners keep their shape, the edges stretch, and the bottom edge is split once more
  so the notch slides to point at the penguin. It is put together once per size and kept.
- **The effect is separate pieces, moved by code.** Generated art supplies only stills: strips that tile end to
  end, and single sprites. The app moves them on a fixed timeline, so every loop closes by construction, and
  `BubbleArt.loop_period()` is the time after which the whole picture repeats exactly.
- **Nothing covers the text.** Effects are drawn on and just outside the border line; the text area is never
  drawn over (measured: `inside` is 0 in the table below).
- **Animation off** (`bubble_effects = false`, or "Animate bubbles" in the menu) draws the still alone.
- `../../chatmon/styles.py` holds each style's text, button and entry colours, matched to its mock-up.

### The moving parts

| Layer (`manifest.json` `fx` type) | What it draws | Why its loop closes |
| --- | --- | --- |
| `scroll` | A tileable strip drifting along the whole border, turned through the corners in thin slices. | A whole number of tiles fit round the border (the strip is scaled a little to fit each bubble size). In time it is two copies half a cycle apart; each drifts at the wanted speed and is at weight 0 at the moment it steps back. |
| `glow` | The still's own rim added to itself on a sine. | A sine of the cycle. |
| `flames` | A baked loop of a flame row, tiled along the top edge and faded out before the corners, drawn behind the bubble's edge. Neighbouring frames are cross-faded. | Baked in `bubble-cut.py` by pushing ONE painted row through noise that climbs exactly one of its own heights per loop. |
| `swap` | The same rim in turned colours, faded in and out. Transparent wherever nothing changes. | A cosine of the cycle. |
| `sheen` | Glints that glide a short way along the border line and fade: the line added to itself inside a soft spot. | Each glint has a fixed slot on the cycle. |
| `runner` | Pulses of light running round the whole border: a strip's pattern and a soft band of colour, shown only under a moving head-and-tail envelope. | Each pulse goes a whole number of times round per cycle, whatever the bubble's size. |
| `wake` | Arcs that strike at set places on the straight edges as a `runner`'s head passes, crackle and fade. | Each place fires once per head per cycle. |
| `arcs`, `sparkles`, `embers` | Single sprites shown at set places on fixed slots of the cycle. | Fixed slots; places come from a hash of the slot number. |
| `crawler` | The caterpillar: a baked gait loop walking the top edge, fading in and out at the ends. | The gait is baked from ONE sprite by a wave that runs tail to head once per stride; the walk and rest are rounded up to whole strides. |

### Each style

| Style | Pieces | How it moves | Cycle |
| --- | --- | --- | --- |
| electric | `electric-current.png` (strip), `electric-arcs.png` (6 sprites), both turned from the painted cyan to yellow by the cutter | The cyan neon edge stays as painted and breathes a little (two slow sines). Two pulses of yellow lightning, half the border apart, run right round it, each once in 8 s (about 110 px/s at the sample size): a hot point with a tail fading over about 190 px, painted over the edge (not added to it) so the yellow shows on the cyan, and masked off the notch's mouth. Where a pulse has just passed, a short arc strikes at a set place on a straight edge, crackles for 0.6 s and fades. | 8 s |
| fire | `fire-flames.png` (36-frame baked loop), `fire-embers.png` (6 sprites) | A low line of flames along the top edge only, rising up to about 15 px, standing taller and lower in slow patches; the ember edge glows on two slow sines; five embers a cycle lift off the top and die within 15 px. | 3 s |
| ghost | `ghost-mist-a.png`, `ghost-mist-b.png` (strips) | Two mist strips drift opposite ways round the rim (11 and 7 px/s) and breathe out of step; the rim glows slowly. Nothing is drawn across the notch's mouth. | 6 s |
| fairy | `fairy-still-b.png` (rim in turned colours), `fairy-sparkles.png` (6 sprites) | The opal edge's colours drift to their opposite and back; two soft glints a cycle glide about 90 px along the border line; four star glints swell, turn a little and fade at set places. | 6 s |
| leaf | `leaf-crawler.png` (42-frame baked gait, its greens toned toward the ivy) | The ivy stays as painted. A caterpillar inches along the top vine at 10 px/s, a hump passing down its body every 1.4 s, and is out of sight for a few seconds before it starts again. | the walk: about 34 s at the sample size (it depends on the bubble's width); the gait repeats every 1.4 s |

## Why not frame sheets

The first version asked the generator for each bubble as a 6-frame animated sheet and cross-faded the frames. It
failed, and the reasons are worth keeping:

- **A generator redraws; it does not move.** Each cell is a fresh drawing of the effect, so the mist, flames or
  crackle in frame 2 is not frame 1's moved a little: played back, the border boils. Frame 6 does not run into
  frame 1 either, whatever the prompt says.
- **Six frames cannot be both smooth and calm.** Played fast they jump; played slowly with cross-fades they
  pulse. The QC below scores a 6-frame sheet at 8 fps at flicker 0.44 against a limit of 0.10.
- **The bubble itself wanders between cells**, so the box wobbles unless every cell is re-aligned.

So looping motion is never generated as frames. The generator paints pieces; code moves them.

Things found while rebuilding it, each now held by a test or by the cutter:

- `QPainter.drawTiledPixmap` places its pattern on whole pixels. A strip drifting a third of a pixel per redraw
  then moves in one-pixel hops. The strips are drawn with a texture brush instead, at a scale that is never
  exactly 1 (`test_a_slow_drift_moves_by_parts_of_a_pixel`).
- Scrolling a whole tile per cycle fixes the speed at tile / cycle (25 to 56 px/s here): too fast. The two-copy
  drift above breaks that tie, so a strip can move as slowly as wanted.
- A painted strip laid whole along a border this small has features a few pixels apart: flames read as a
  fringe, mist as a ruffle. The cutter uses part of each strip, drawn longer (`part`, `stretch`).
- Adding a see-through glow to itself makes it more solid: on a light desktop the first sheen was a white smear.
  The sheen now uses only the nearly solid border line, strongest on the line and fading either side.
- Art at twice display size must be cut on even pixels, or two 9-slice pieces meet on a half pixel and a bright
  tick shows at the join (`test_cut_lines_fall_on_whole_display_pixels`).
- A loop whose activity rises and falls must have its seam judged against the steps either side of it, not
  against the median step.

## Loop QC

`python art/tools/loop-qc.py OUT_DIR` renders one whole cycle of every style through the app's own drawing code,
at real size (a 300 x 92 px text area) and 30 redraws a second, over a dark and a light desktop, and fails if any
gated measure is over its limit. What each measure means is in the tool's own header. Limits, the same for every
style: cycle 3 to 8 s (the leaf's walk up to 60 s), jump 2.5, seam 1.5, flash 1.5, closes 0.05, flicker 0.10,
pop 60, inside 0, light 0.08. The electric style is measured without its running lightning (`-run`, gated like the rest)
and with it (`+run`: flicker, pop and jump reported only, since a pulse passing a pixel and an arc striking are
fast changes on purpose; flash stays gated). Whether the pulses' speed looks right is judged by watching. `boil` is printed
and not gated, for the reason given in the tool.

```
style           bg     cycle  step  jump  seam flash closes flicker  boil  pop inside  light  verdict
electric-run    dark    4.0s  0.09  1.95  1.42  0.18  0.000   0.008  1.00    2    0.0  0.006  ok
electric-run    light   4.0s  0.11  1.81  1.35  0.19  0.000   0.023  1.00    2    0.0  0.001  ok
electric+run    dark    8.0s  0.54  2.24  1.07  1.22  0.000   0.078  1.00  155    0.0  0.006  ok
electric+run    light   8.0s  0.52  2.01  1.07  1.04  0.000   0.064  1.00  103    0.0  0.002  ok
fire            dark    3.0s  0.25  1.60  1.21  0.40  0.000   0.019  1.00   33    0.0  0.013  ok
fire            light   3.0s  0.30  1.58  1.17  0.47  0.000   0.040  1.00   35    0.0  0.002  ok
ghost           dark    6.0s  0.24  1.27  1.08  0.30  0.000   0.003  1.00    4    0.0  0.003  ok
ghost           light   6.0s  0.24  1.31  1.09  0.32  0.000   0.008  1.00    4    0.0  0.003  ok
fairy           dark    6.0s  0.13  1.41  0.00  0.19  0.000   0.001  1.00    8    0.0  0.007  ok
fairy           light   6.0s  0.14  1.27  0.00  0.18  0.000   0.028  1.00    6    0.0  0.000  ok
leaf            dark   33.6s  0.05  1.22  0.00  0.06  0.000   0.050  1.00   25    0.0  0.000  ok
leaf            light  33.6s  0.08  1.32  0.00  0.11  0.000   0.031  1.00   35    0.0  0.001  ok
```

The measures themselves were checked on loops whose answer is known:

```
case                                            jump   seam flash closes flicker  pop  verdict
good: slow drift, 45 px/s, whole tile per cycle  1.08   1.00  1.20  0.000   0.001   16  ok
good: slow sine glow on a texture, +-15%        1.45   1.00  0.18  0.000   0.001    2  ok
known false alarm: the same glow on one flat colour  4.78   2.00  0.24  0.000   0.001    1  FAIL jump, seam
bad: fast scroll 360 px/s                       1.08   1.02  9.16  0.000   0.568  120  FAIL flash, flicker, pop
bad: 6-frame sheet at 8 fps (boil)             349.79 309.81 17.49  0.000   0.436  236  FAIL jump, seam, flash, flicker, pop
bad: loop does not close (drift 0.9 tile)       1.08   9.47 18.68 18.363   0.019  222  FAIL seam, flash, closes, pop
bad: one-frame full flash                      478.33   0.00 23.92  0.000   0.864  100  FAIL jump, flash, flicker, pop
```

The cutter's own checks on the pieces (a strip's wrap column against its other columns; a baked loop's last step
against the steps either side):

```
  electric-current.png: 660 x 24 art px, tile 330 display px, wrap step x0.53 of the strip's own 99th percentile: ok
  fire-flames.png: 36 frames of 375 x 42 art px, tile 188 display px, loop seam x1.03 of the steps either side, wrap x0.49: ok
  ghost-mist-a.png: 413 x 38 art px, tile 206 display px, wrap step x0.49 of the strip's own 99th percentile: ok
  ghost-mist-b.png: 516 x 28 art px, tile 258 display px, wrap step x0.52 of the strip's own 99th percentile: ok
  leaf-crawler.png: 42 frames of 68 x 36 art px, gait seam x1.00 of the steps either side: ok
```

Drawing cost, one redraw of the sample bubble (measured with `QImage` as the target, Qt's software painter):

```
style     scale    size px still ms  mean ms  p95 ms worst ms  share of a 33 ms redraw
electric    1.0   364x166      0.02     1.18    1.44     4.12  4%
electric    2.0   728x332      0.08     2.11    2.97     5.15  6%
fire        1.0   350x166      0.03     0.26    0.33     0.52  1%
fire        2.0   700x332      0.08     0.50    0.55     0.60  1%
ghost       1.0   359x164      0.02     1.08    1.24     1.68  3%
ghost       2.0   718x328      0.08     2.02    2.49     3.09  6%
fairy       1.0   352x154      0.03     0.16    0.22     0.80  0%
fairy       2.0   704x308      0.07     0.27    0.37     0.66  1%
leaf        1.0   363x185      0.03     0.07    0.08     0.18  0%
leaf        2.0   726x370      0.08     0.12    0.14     0.26  0%
```

## Tools

| Tool | What it does |
| --- | --- |
| `../tools/bubble-cut.py RAW_DIR` | Builds everything in `chatmon/bubbles/` from the picked originals: the still (median of the sheet's cells, cut on even pixels, straight edges evened), the rim's measured line, the tileable strips (ends folded over each other along a wandering edge, then proved by the wrap-column check), the baked flame loop and caterpillar gait, the sprite rows, and `manifest.json`. Stops on an original without real transparency, a strip whose join shows, or a baked loop that does not close. |
| `../tools/bubble-preview.py OUT_DIR` | Renders every style at real size and real speed with real text and buttons over a dark and a light desktop (`.webp`, `.gif`), a contact sheet and the stills. |
| `../tools/loop-qc.py OUT_DIR` | The measured loop check above; also writes a strip of 12 moments and a seam sheet (last three and first three frames) per style. |

RAW_DIR holds `<style>-anim.png` (the picked bubble sheets) and the effect originals named in the cutter's header.
The originals are not in this repository; like the penguin's raw sheets, they belong in the raw-art archive.

## Picks

| Style | Mock-up picked | Bubble sheet used for the still |
| --- | --- | --- |
| electric | option 1, navy glass with a cyan neon edge | try b |
| fire | option 1, charred panel with an ember edge | try a |
| ghost | option 3, frosted smoky panel with a pale violet rim | try b |
| fairy | option 2, blush panel with an iridescent opal edge | try a |
| leaf | option 3, off-white with a dark green edge and ivy | try a |

## Prompts

### The mock-ups

Each mock-up prompt was the shared text below with the style's panel and effect filled in. The picked ones:

**electric** (`electric-1`):

> Create ONE high-quality UI design mockup on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It shows ONE speech bubble from a desktop assistant app for Pokemon fans: slightly cute but professional and polished, never childish. The bubble is ONE SINGLE PIECE: a wide rounded-rectangle panel about 2.4 times as wide as it is tall, taking about 78 percent of the image width, with its tail growing out of the bottom edge a little left of the middle as part of the same shape; the border runs continuously round the tail with NO line across the join, and the fill flows straight into the tail. NO emblems, ornaments, gems or decorations on the corners: the corners are clean and simply rounded. A deep navy glass panel with a thin glowing cyan neon edge. Effect, caught mid-animation: fine white-cyan electric crackle running tightly along the edge, with one small yellow spark. The effect hugs the border tightly, within a few pixels of it, never spilling far out and never covering the inside. Inside, laid out like a real app: top left a bold title 'Sparky', a small close cross at the top right, one line of body text 'Your build finished. All 98 tests passed.', and bottom right two compact buttons labelled 'Open' and 'Later', designed in the same style as the bubble (dark glass with a thin cyan edge, the first one lit). All text crisp and spelled exactly as given. Modern, premium UI quality like a top-tier game's interface: clean, sharp, refined, soft lighting, readable on both a light (#E9EBF0) and a dark (#1E2128) desktop. Nothing touches the image edges. Landscape 3:2 image.

**fire** (`fire-1`):

> Create ONE high-quality UI design mockup on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It shows ONE speech bubble from a desktop assistant app for Pokemon fans: slightly cute but professional and polished, never childish. The bubble is ONE SINGLE PIECE: a wide rounded-rectangle panel about 2.4 times as wide as it is tall, taking about 78 percent of the image width, with its tail growing out of the bottom edge a little left of the middle as part of the same shape; the border runs continuously round the tail with NO line across the join, and the fill flows straight into the tail. NO emblems, ornaments, gems or decorations on the corners: the corners are clean and simply rounded. A charred, very dark warm panel with a thin glowing ember edge. Effect, caught mid-animation: small, tight flames licking along the edge, mostly along the top. The effect hugs the border tightly, within a few pixels of it, never spilling far out and never covering the inside. Inside, laid out like a real app: top left a bold title 'Sparky', a small close cross at the top right, one line of body text 'Your build finished. All 98 tests passed.', and bottom right two compact buttons labelled 'Open' and 'Later', designed in the same style as the bubble (dark with a thin ember-orange edge). All text crisp and spelled exactly as given. Modern, premium UI quality like a top-tier game's interface: clean, sharp, refined, soft lighting, readable on both a light (#E9EBF0) and a dark (#1E2128) desktop. Nothing touches the image edges. Landscape 3:2 image.

**ghost** (`ghost-3`):

> Create ONE high-quality UI design mockup on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It shows ONE speech bubble from a desktop assistant app for Pokemon fans: slightly cute but professional and polished, never childish. The bubble is ONE SINGLE PIECE: a wide rounded-rectangle panel about 2.4 times as wide as it is tall, taking about 78 percent of the image width, with its tail growing out of the bottom edge a little left of the middle as part of the same shape; the border runs continuously round the tail with NO line across the join, and the fill flows straight into the tail. NO emblems, ornaments, gems or decorations on the corners: the corners are clean and simply rounded. A frosted smoky dark panel with a pale violet rim. Effect, caught mid-animation: faint ghostly mist trails flowing round the rim. The effect hugs the border tightly, within a few pixels of it, never spilling far out and never covering the inside. Inside, laid out like a real app: top left a bold title 'Sparky', a small close cross at the top right, one line of body text 'Your build finished. All 98 tests passed.', and bottom right two compact buttons labelled 'Open' and 'Later', designed in the same style as the bubble (frosted dark glass with a pale violet edge). All text crisp and spelled exactly as given. Modern, premium UI quality like a top-tier game's interface: clean, sharp, refined, soft lighting, readable on both a light (#E9EBF0) and a dark (#1E2128) desktop. Nothing touches the image edges. Landscape 3:2 image.

**fairy** (`fairy-2`):

> Create ONE high-quality UI design mockup on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It shows ONE speech bubble from a desktop assistant app for Pokemon fans: slightly cute but professional and polished, never childish. The bubble is ONE SINGLE PIECE: a wide rounded-rectangle panel about 2.4 times as wide as it is tall, taking about 78 percent of the image width, with its tail growing out of the bottom edge a little left of the middle as part of the same shape; the border runs continuously round the tail with NO line across the join, and the fill flows straight into the tail. NO emblems, ornaments, gems or decorations on the corners: the corners are clean and simply rounded. A soft blush panel with an iridescent opal edge. Effect, caught mid-animation: delicate sparkle glints dancing along the border. The effect hugs the border tightly, within a few pixels of it, never spilling far out and never covering the inside. Inside, laid out like a real app: top left a bold title 'Sparky', a small close cross at the top right, one line of body text 'Your build finished. All 98 tests passed.', and bottom right two compact buttons labelled 'Open' and 'Later', designed in the same style as the bubble (blush with an opal edge, the first one filled). All text crisp and spelled exactly as given. Modern, premium UI quality like a top-tier game's interface: clean, sharp, refined, soft lighting, readable on both a light (#E9EBF0) and a dark (#1E2128) desktop. Nothing touches the image edges. Landscape 3:2 image.

**leaf** (`leaf-3`):

> Create ONE high-quality UI design mockup on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It shows ONE speech bubble from a desktop assistant app for Pokemon fans: slightly cute but professional and polished, never childish. The bubble is ONE SINGLE PIECE: a wide rounded-rectangle panel about 2.4 times as wide as it is tall, taking about 78 percent of the image width, with its tail growing out of the bottom edge a little left of the middle as part of the same shape; the border runs continuously round the tail with NO line across the join, and the fill flows straight into the tail. NO emblems, ornaments, gems or decorations on the corners: the corners are clean and simply rounded. An off-white paper panel with a slim dark-green edge line; delicate ivy with small glossy leaves grows along the border. Effect, caught mid-animation: the ivy grows a little further and a small, naturally drawn caterpillar (not cartoonish) crawls along it on the top edge. The effect hugs the border tightly, within a few pixels of it, never spilling far out and never covering the inside. Inside, laid out like a real app: top left a bold title 'Sparky', a small close cross at the top right, one line of body text 'Your build finished. All 98 tests passed.', and bottom right two compact buttons labelled 'Open' and 'Later', designed in the same style as the bubble (off-white with a dark green outline). All text crisp and spelled exactly as given. Modern, premium UI quality like a top-tier game's interface: clean, sharp, refined, soft lighting, readable on both a light (#E9EBF0) and a dark (#1E2128) desktop. Nothing touches the image edges. Landscape 3:2 image.

### The bubble sheets

Each was made from its picked mock-up, attached as the design. They were asked for as 6-frame animations; they
are now only the source of the still bubble (the per-pixel median of the six cells). See "Why not frame sheets".

**electric** (`electric-anim-b`):

> The attached image is the APPROVED design of a speech bubble (a UI mockup). Recreate ONLY the bubble itself, matching it exactly: the same shape and proportions, the same border, colours, materials, fill and glow, and the same tail (notch) as part of the same piece with the border running continuously round it and no line across the join, at the same place on the bottom edge. Make it EMPTY: NO title, NO text, NO close cross, NO buttons; the inside is plain fill. Create ONE SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells (3 columns, 2 rows), frames 1 to 6 of ONE seamless looping animation of this bubble's border effect, read left to right, top row first; frame 6 flows straight into frame 1. In every cell the bubble is drawn identically, about 76 percent of the cell width, centred, at exactly the same position and size; only the effect changes from frame to frame. EFFECT: fine white-cyan electric crackle runs along the neon edge, jumping to new places in every frame, with now and then one small yellow spark. The effect hugs the border tightly, within a few pixels of it, and never covers the inside. NO grid lines, NO cell borders, NO numbers, NO text. Nothing crosses into a neighbouring cell or touches a cell edge. Premium, polished, professional UI art. Landscape 2:1 image.

**fire** (`fire-anim-a`):

> The attached image is the APPROVED design of a speech bubble (a UI mockup). Recreate ONLY the bubble itself, matching it exactly: the same shape and proportions, the same border, colours, materials, fill and glow, and the same tail (notch) as part of the same piece with the border running continuously round it and no line across the join, at the same place on the bottom edge. Make it EMPTY: NO title, NO text, NO close cross, NO buttons; the inside is plain fill. Create ONE SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells (3 columns, 2 rows), frames 1 to 6 of ONE seamless looping animation of this bubble's border effect, read left to right, top row first; frame 6 flows straight into frame 1. In every cell the bubble is drawn identically, about 76 percent of the cell width, centred, at exactly the same position and size; only the effect changes from frame to frame. EFFECT: small, tight flames lick along the glowing ember edge, mostly along the top edge and a little up the sides, flickering and changing shape in every frame. The effect hugs the border tightly, within a few pixels of it, and never covers the inside. NO grid lines, NO cell borders, NO numbers, NO text. Nothing crosses into a neighbouring cell or touches a cell edge. Premium, polished, professional UI art. Landscape 2:1 image.

**ghost** (`ghost-anim-b`):

> The attached image is the APPROVED design of a speech bubble (a UI mockup). Recreate ONLY the bubble itself, matching it exactly: the same shape and proportions, the same border, colours, materials, fill and glow, and the same tail (notch) as part of the same piece with the border running continuously round it and no line across the join, at the same place on the bottom edge. Make it EMPTY: NO title, NO text, NO close cross, NO buttons; the inside is plain fill. Create ONE SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells (3 columns, 2 rows), frames 1 to 6 of ONE seamless looping animation of this bubble's border effect, read left to right, top row first; frame 6 flows straight into frame 1. In every cell the bubble is drawn identically, about 76 percent of the cell width, centred, at exactly the same position and size; only the effect changes from frame to frame. EFFECT: faint, soft violet mist trails drift and curl along the pale rim, flowing slowly round it from frame to frame. The effect hugs the border tightly, within a few pixels of it, and never covers the inside. NO grid lines, NO cell borders, NO numbers, NO text. Nothing crosses into a neighbouring cell or touches a cell edge. Premium, polished, professional UI art. Landscape 2:1 image.

**fairy** (`fairy-anim-a`):

> The attached image is the APPROVED design of a speech bubble (a UI mockup). Recreate ONLY the bubble itself, matching it exactly: the same shape and proportions, the same border, colours, materials, fill and glow, and the same tail (notch) as part of the same piece with the border running continuously round it and no line across the join, at the same place on the bottom edge. Make it EMPTY: NO title, NO text, NO close cross, NO buttons; the inside is plain fill. Create ONE SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells (3 columns, 2 rows), frames 1 to 6 of ONE seamless looping animation of this bubble's border effect, read left to right, top row first; frame 6 flows straight into frame 1. In every cell the bubble is drawn identically, about 76 percent of the cell width, centred, at exactly the same position and size; only the effect changes from frame to frame. EFFECT: delicate sparkle glints twinkle in and out along the iridescent opal edge, a few at a time, in new places in every frame. The effect hugs the border tightly, within a few pixels of it, and never covers the inside. NO grid lines, NO cell borders, NO numbers, NO text. Nothing crosses into a neighbouring cell or touches a cell edge. Premium, polished, professional UI art. Landscape 2:1 image.

**leaf** (`leaf-anim-a`):

> The attached image is the APPROVED design of a speech bubble (a UI mockup). Recreate ONLY the bubble itself, matching it exactly: the same shape and proportions, the same border, colours, materials, fill and glow, and the same tail (notch) as part of the same piece with the border running continuously round it and no line across the join, at the same place on the bottom edge. Make it EMPTY: NO title, NO text, NO close cross, NO buttons; the inside is plain fill. Create ONE SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells (3 columns, 2 rows), frames 1 to 6 of ONE seamless looping animation of this bubble's border effect, read left to right, top row first; frame 6 flows straight into frame 1. In every cell the bubble is drawn identically, about 76 percent of the cell width, centred, at exactly the same position and size; only the effect changes from frame to frame. EFFECT: the ivy leaves along the border sway gently and a small tendril curls; there is NO caterpillar and no insect anywhere. The effect hugs the border tightly, within a few pixels of it, and never covers the inside. NO grid lines, NO cell borders, NO numbers, NO text. Nothing crosses into a neighbouring cell or touches a cell edge. Premium, polished, professional UI art. Landscape 2:1 image.

### The caterpillar

Made from the earlier caterpillar sheet (attached) to be less cutesy. Only its last cell, the flat pose, is used:
the crawl is baked from that one sprite.

> Create ONE game sprite sheet on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 4x2 grid of 8 equally sized cells (4 columns, 2 rows), read left to right then top to bottom. NO grid lines, NO cell borders, NO numbers, NO text. Nothing may cross into a neighbouring cell or touch a cell edge: keep a clear transparent gutter round every cell. The 8 cells are frames 1 to 8 of ONE seamless looping CRAWLING CATERPILLAR animation, side view facing right, crawling along a flat invisible line near the bottom of each cell: a plump leaf-green caterpillar with seven round body segments with lighter yellow-green bellies, a round head with small dark eyes and two short antennae and little stubby feet. It moves like a wave: a hump travels from the tail to the head over the 8 frames, the segments rippling, so frame 8 flows straight into frame 1. Its feet touch the same baseline and its head stays at the same horizontal spot in every cell. It fills about 75 percent of the cell width. Nothing else in the cells: no leaf, no ground, no shadow. Style: polished, lightly stylized game art with a thin dark outline, soft cel shading and bright clean colours, readable at 24 px on both a light (#E9EBF0) and a dark (#1E2128) desktop. Landscape 2:1 image. Use the attached sheet as the reference for the exact grid, poses, frame timing and placement, but make the creatures LESS CUTESY: more natural, lightly stylized insect proportions like polished nature illustration in a premium game, small dark natural eyes, NO blush, NO smiles or mouths, NO oversized heads, NO big cartoon eyes. Keep the clean outline and bright readable colours.

### The effect pieces

Each was generated on its own, on a transparent background, with the shared ending "Polished, premium ...":

**ghost: the broader mist strip** (`ghost-mist-a.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It is a single long horizontal STRIP of soft ghostly MIST, made to be tiled end to end as a game UI border effect. The strip runs straight across the FULL width of the image, from the left image edge to the right image edge, at the vertical centre, with even density and brightness along its whole length: no beginning, no end, no fading or tapering at the sides; it must run off both the left and the right edge. Slow rolling billows of translucent pale lavender (#D6C8FF) and violet (#9A7BFF) mist with a little white, curling gently a short way above and below a faint centre line; never more than about 60 percent opaque, with soft edges fading to nothing. The band of mist is about 30 percent of the image height. Everything else in the image is fully transparent. No frame, no panel, no border box, no text, no icons. Polished, premium, semi-realistic stylized game VFX, soft glows semi-transparent. Landscape 3:1 image.

**ghost: the finer wisp strip** (`ghost-mist-b.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It is a single long horizontal STRIP of fine ghostly WISPS, made to be tiled end to end as a game UI border effect. The strip runs straight across the FULL width of the image, from the left image edge to the right image edge, at the vertical centre, with even density and brightness along its whole length: no beginning, no end, no fading or tapering at the sides; it must run off both the left and the right edge. Thin, delicate curling wisps and tendrils of translucent lavender (#D6C8FF) and violet (#9A7BFF) vapour drifting along a faint centre line, lighter and finer than fog, never more than about 50 percent opaque, fading to nothing. The band is about 25 percent of the image height. Everything else in the image is fully transparent. No frame, no panel, no border box, no text, no icons. Polished, premium, semi-realistic stylized game VFX, soft glows semi-transparent. Landscape 3:1 image.

**electric: the current strip** (`electric-current.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It is a single long horizontal STRIP of ELECTRIC CURRENT, made to be tiled end to end as a game UI border effect. The strip runs straight across the FULL width of the image, from the left image edge to the right image edge, at the vertical centre, with even density and brightness along its whole length: no beginning, no end, no fading or tapering at the sides; it must run off both the left and the right edge. A thin continuous glowing line of cyan electricity: a white-hot hairline core with a cyan (#3FCAF2) glow, finely irregular and crackling, with many tiny branching filaments that stay close to the line (no large arcs, no bolts leaving the line). The whole effect is thin: about 12 percent of the image height. Everything else in the image is fully transparent. No frame, no panel, no border box, no text, no icons. Polished, premium, semi-realistic stylized game VFX, soft glows semi-transparent. Landscape 3:1 image.

**electric: the arc sprites (made earlier as `electric-fx`; the two yellow arcs are left out)** (`electric-arcs.png`):

> Create ONE game VFX SPRITE SHEET on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 4x2 grid of 8 equally sized cells (4 columns, 2 rows), read left to right then top to bottom. NO grid lines, NO cell borders, NO numbers, NO text. Nothing may cross into a neighbouring cell or touch a cell edge: keep a clear transparent gutter round every cell. Each cell holds ONE separate short ELECTRIC ARC lying horizontally across the middle of the cell, about 80 percent of the cell width and thin: a jagged crackling lightning bolt with one or two small forks, a hot white core and a glow in cyan (#3FCAF2) on cells 1, 2, 3, 5, 6, 7 and in yellow (#FFD23A) on cells 4 and 8. Every arc a different jagged shape; both ends fade out to nothing. Style: polished, vibrant, semi-realistic stylized game VFX like a top-tier match-3 game, clean silhouettes, glowing parts semi-transparent where soft, readable at 24 px on both a light (#E9EBF0) and a dark (#1E2128) desktop. Landscape 2:1 image.

**fire: the flame row (`fire-flames-b`; a first try, `fire-flames-a`, asked for taller tongues and was not used)** (`fire-flames.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop). It is a single long horizontal STRIP of small FLAMES, made to be tiled end to end as a game UI border effect. The strip runs straight across the FULL width of the image, from the left image edge to the right image edge, at a flat straight baseline one third of the way up from the bottom, with even density and brightness along its whole length: no beginning, no end, no fading or tapering at the sides; it must run off both the left and the right edge. A continuous low row of small flickering flames along the baseline, like a line of fire along the edge of a hot coal: short pointed tongues leaning slightly different ways, hot yellow-white cores, orange (#FF8A1F) bodies and red-orange (#E04A1A) translucent tips, a thin bright ember line along the baseline. Flames only rise upward; nothing below the baseline. The tallest flames are about 25 percent of the image height. Everything else in the image is fully transparent. No frame, no panel, no border box, no text, no icons. Polished, premium, semi-realistic stylized game VFX, soft glows semi-transparent. Landscape 3:1 image.

**fire: the ember sprites** (`fire-embers.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells, each holding ONE separate small sprite centred in its cell with clear empty space around it; nothing touches a cell edge. NO grid lines, NO borders, NO numbers, NO text. Six different small glowing EMBER SPARKS: tiny bits of burning ember, each a hot yellow-white core with an orange glow, slightly different shapes (round, oval, a short streak, a tiny shard), soft glow fading to nothing. Polished, premium, refined game VFX, not cartoonish. Landscape 3:2 image.

**fairy: the glint sprites** (`fairy-sparkles.png`):

> Create ONE image on a fully TRANSPARENT background (real alpha: every background pixel fully transparent, no checkerboard, no backdrop): a strict 3x2 grid of 6 equally sized cells, each holding ONE separate small sprite centred in its cell with clear empty space around it; nothing touches a cell edge. NO grid lines, NO borders, NO numbers, NO text. Six different elegant SPARKLE GLINTS like light glinting off a jewel: thin four-point and six-point star glints with a tiny bright white core and fine tapering rays, in soft tints (two white-gold, two rose pink, two pale opal blue-violet), delicate and jewelry-like, with a faint soft halo. Polished, premium, refined game VFX, not cartoonish. Landscape 3:2 image.
