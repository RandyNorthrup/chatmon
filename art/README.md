# The penguin's art

An opt-in desktop pet built from the owner's own character: an electric
penguin, charcoal with a cream face and belly and a white penguin mark,
orange ear tufts, beak and toe claws, blue armour plates with yellow
lightning bolts, and glowing cyan nodes on the collar and flippers. It is
not a Meta character, name or likeness.

The companion was designed for Muse Desktop in
[muse-spark-code](https://github.com/RandyNorthrup/muse-spark-code) (plan
D91.30), where it walks along the status bar, reacts to the agent, and peeks
up from behind the status bar while hidden. This repository holds the
character's art: the reference sheet, the prompts and tools that made the
animations, and how they were made. The animation strips themselves live in
[`../chatmon/anim/`](../chatmon/anim), where the app loads
them; paths below are relative to this folder.

The chat bubbles' art has its own notes in [`bubbles/README.md`](bubbles/README.md). The four other
companions' concept sheets are in [`concepts/`](concepts/README.md); their strips, and the tools that
cut and check them, are described under "The four other companions" below.

## Files

| Path                         | What it is                                                                                                        |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `source/reference-sheet.jpg` | The owner's character sheet (front, side, jump, charge, beam and angry poses), as supplied on 2026-10-05.         |
| `../chatmon/anim/<name>.png` | One horizontal strip per animation, 240 px tall, frames left to right, transparent background. |
| `../chatmon/anim/manifest.json` | Per animation: `frames`, the frame width `w` and height `h` in pixels, the playback rate `fps`, `loop`, the display `scale`, and `touchup` once `penguin-touchup.py` has fixed the strip. |
| `tools/penguin-slice.py`     | Keys the chroma-green sheets, slices each grid into frames, lines every frame's body up with frame 1's, and writes the strips and the manifest (`--only <name>` re-makes one). |
| `tools/penguin-touchup.py`   | The pixel fixes, run over the strips after slicing (see "Fixes" below).                                          |
| `tools/spritefix.py`         | What the two scripts share: despill, per-frame alignment, the edge fade, the foot recolour and the bolt halo.     |
| `tools/penguin-cut.py`       | Cuts the six reference poses out of `source/reference-sheet.jpg` (used to check the strips against the original). |
| `prompts.md`                 | The exact image prompts that produced the sheets, including the 2026-11-09 `beam` redraw.                       |

Frame `i` of an animation is the `w` × `h` rectangle at `x = i * w` in its
strip.

## The twelve animations

| Name     | Frames | fps | Loops | Used for                                                       |
| -------- | -----: | --: | :---: | -------------------------------------------------------------- |
| `walk`   |      8 |  10 |  yes  | Walking along the status bar (facing right; mirrored for left) |
| `idle`   |      6 |   5 |  yes  | Standing still, blinking every 3 to 5 s (see below)            |
| `peek`   |      6 |   4 |  no   | Peeking up from behind the status bar while hidden             |
| `talk`   |      6 |   8 |  yes  | Answering                                                      |
| `wave`   |      6 |   7 |  yes  | Greeting                                                       |
| `think`  |      6 |   4 |  yes  | Waiting for an answer (frames 1-5); frame 6, "got it!", once as the answer arrives |
| `hop`    |      6 |   9 |  yes  | A finished turn (when agent reactions are on)                  |
| `sleep`  |      6 |   3 |  yes  | Inactivity                                                     |
| `charge` |      6 |   9 |  yes  | Working (a long task running)                                  |
| `alert`  |      6 |   8 |  yes  | Something needs the person (points to a waiting approval)      |
| `turn`   |      6 |   6 |  no   | Turning between right, front and left; frame 6, a little hop facing left, now and then when it stops while facing left |
| `beam`   |      6 |   8 |  no   | Celebrating (a merge, a green check)                           |

The app plays some strips in its own order (`../chatmon/behavior.py`):
`idle` holds frame 1 for a random 3 to 5 s, then blinks through frames 3, 4
and 5 at 10 fps (frames 2 and 6 aren't used); `think` loops frames 1 to 5
and keeps frame 6 for the moment the answer arrives; `sleep` dozes off through
frames 1 to 3 and loops 4 to 6.

The sheets were drawn at slightly different scales, so the manifest gives each
animation a display `scale` that keeps the penguin one size on screen. They
were matched by standing height against `idle` (the ear-tuft span used at
first changes with the pose, and made the penguin shrink when it talked):
`hop` 1.13, `charge` 1.17, `alert` 1.05, `peek` 0.47 (matched by head width),
the rest 1. `tools/penguin-slice.py` writes the same values.

## How the sheets were made

1. The owner's reference sheet was uploaded to an image-generation chat in
   the owner's own ChatGPT account on 2026-10-05.
2. Each prompt in `prompts.md` asked for one sprite sheet in a fixed grid
   (walk 4 × 2, the others 3 × 2) on a flat chroma-key green (#00B140), with
   the same character size, camera and baseline in every frame, and no
   shadows, text or grid lines.
3. `tools/penguin-slice.py` removed the green, cut the grid, aligned each row
   by its lowest opaque pixel, cropped every frame to the union box of its
   animation, and wrote the strips at 240 px into `../chatmon/anim/`.
   Since 2026-11-09 it also lines up every frame, not just every row (see
   "Fixes").
4. `tools/penguin-touchup.py` applied the pixel fixes (2026-11-09).

Under OpenAI's terms of use the person who prompts owns the output; the
character itself is the owner's. Before the art ships anywhere, record this
provenance in that product's third-party notices. The white belly mark was
checked against publishers' penguin logos on 2026-11-09 (the owner's check:
done).

## Fixes (2026-11-09)

An art review found these; all are fixed in the strips, and the two tools
make the same fixes on a re-slice (`penguin-slice.py`, then
`penguin-touchup.py`).

- **The penguin slid sideways in most loops.** The generator didn't centre the
  character in every column of a sheet, and the slicer only lined up rows, so
  frames 2-3 and 5-6 sat up to 28 px (at 240 px) left of frame 1 and the
  penguin shuffled and snapped back every loop. Every frame is now shifted so
  the body stays put, by an anchor that suits the animation
  (`spritefix.ALIGN`): the white belly mark for `hop` and `alert`, the best
  overlap of the body's own colours for the other front views, the middle of
  the body for `walk` (so swinging feet don't pull it), the feet for `turn`
  and `beam` (the point the app pins to the floor), and the head at
  the cut line for `peek`. The spread, in strip pixels, before and after:
  `talk` 28 to 0, `sleep` 26 to 0, `hop` 24 to 0, `wave` 23 to 0, `turn` 22 to 0,
  `alert` 16 to 0, `think` 14 to 0, `idle` 13 to 0, `walk` 12 to 0, `peek` 10 to 0,
  `charge` 3 to 0; `beam`'s feet 33 to 1. `tests/test_anim_strips.py` checks the
  front views stay put.
- **Green fringe.** Edge and gap pixels kept some of the chroma-key green; the
  green is pulled out of every green-hued pixel (the penguin has no green).
- **Walk feet.** The lifted back foot in frames 3, 4, 7 and 8 was drawn olive
  or brown; it is charcoal now, with its orange claws.
- **Charge lightning on a light taskbar.** The pale bolts washed out; a thin
  dark halo behind the bolts that stick out past the body keeps them readable
  on light and is barely visible on dark.
- **Beam.** The first strip's beam ran into the sheet's cell edge in frames 3
  and 4 and ended in a flat vertical cut. The sheet was redrawn from the
  original strip as the exact target (prompt in `prompts.md`), so the penguin,
  its poses and faces stay the owner's, and the beam ends inside every cell.
  It is scaled so the body is the original's height frame by frame and lined
  up by the feet (they move 1 px at most). `penguin-touchup.py` leaves `beam`
  alone (`KEEP`), so a later run can't change it.
- **Blinking and thinking.** `idle` blinked every 1.2 s with its eyes shut or
  closing half the time, and `think` flashed its "got it!" frame every 1.5 s
  while still waiting. Both are fixed in how the app plays the strips (above).

The 2026-11-09 beam sheet isn't in this repository either; it goes with the
other raw sheets.

The raw 1536 × 1024 sheets (19 MB) are not in this repository; they were
archived at `~/archive/companion-sheets/` on the Kubuntu desktop. Re-running
the slicer needs them (`python tools/penguin-slice.py <sheets-dir>`, with
Pillow installed); the strips here are the build input.

## The four other companions (2026-11-09 and 10)

The fire red panda, the ghost rabbit, the leaf pangolin and the fairy axolotl
(concepts in [`concepts/`](concepts/README.md)) have the penguin's twelve
animations, cut to the same pattern: one 240 px strip per animation and a
`manifest.json`, in `../chatmon/anim/<creature>/`. The penguin's own
strips stay in `../chatmon/anim/`, untouched. The app's names are
kept: each creature's signature move is its `beam` strip.

| Path | What it is |
| ---- | ---------- |
| `tools/creatures.json` | The table the tools are driven by: per creature its key colour, its size on screen, the colours that mark its body, belly and effects; per animation the sheet cells that make the frames, what stays put from frame to frame, and its display scale. |
| `tools/creature-cut.py` | Sheets to strips: `penguin-slice.py` made general (any key colour, soft glows, frames taken from several sheets, built frames). |
| `tools/creature-qc.py` | Measures the strips and exits 1 if any is out of limits (below). |
| `tools/creature-preview.py` | Renders previews through the app's own sprite code, for the owner to watch. |
| `tools/creaturespec.py` | What the cutter and the QC share: reading the table, and finding the body, the floor, the anchor and the specks in a frame. |
| `tools/spritefix.py` | The keying, despill, resampling and component code (shared with the penguin's tools, whose part of it is unchanged). |
| `tools/blink-inbetween.py` | Builds a half-closed eye from a creature's own open and closed frames (the ghost rabbit's three built frames). |
| `source/<creature>/*.png` | The approved raw sheets the cutter reads. |
| `source/<creature>/*.txt` | The exact prompt of every sheet in use, and how each built sheet was made. |
| `source/<creature>/sheets.sha1` | The SHA-1 of every raw sheet in use. |

### The raw sheets

Each creature has 12 to 14 raw sheets, 1536 x 1024 like the penguin's: `walk`
is 4 x 2 cells of 384 x 512, the others 3 x 2 cells of 512 x 512, on a flat
key colour. They were generated on 2026-11-09 with the Codex CLI's image
generation (the owner's ChatGPT sign-in) from the concept sheets; the ones cut
here are the approved ones, and their prompts are in `source/<creature>/`.

The sheets are in this repository, in `source/<creature>/` beside their
prompts (about 80 MB in all; the penguin's are not, see above).
`sheets.sha1` in each folder lists them. Re-cut every creature with
`python tools/creature-cut.py source` (from `art/`); run on these sheets it
gives the strips in `../chatmon/anim/<creature>/` byte for byte.

What is not a plain 3 x 2 sheet:

- **fire-red-panda `beam`** is two files, `signature-a.png` and
  `signature-b.png`, of 2 x 2 cells of 768 x 512 (the panda at full size plus
  its fire puff does not fit a 512 px cell): frames 1 to 4 are the four cells
  of `-a`, frames 5 and 6 the top row of `-b`.
- **ghost-rabbit `idle`** takes frames 1, 2, 4 and 6 from `idle.png` and frames
  3 and 5 (the half-closed blink) from `idle_blink_built.png`. Cells 3 and 5
  of `idle.png` are never used: their lids slant and read sly.
- **ghost-rabbit `sleep`** takes frame 1 from `sleep_frame1_built.png` and
  frames 2 to 6 from `sleep.png` (its own cell 1 reads smug).
- **leaf-pangolin `idle`** is the sheet that did not pass its own QC for one
  reason: frame 2 is frame 1 again, with no breath. The cutter builds frame 2
  from frame 1 (below). Its key is magenta, because the creature is green.
- **fairy-axolotl `walk`** is walk candidate t11, the one the owner picked.

### Built frames, and why

Four frames are built from the creature's own drawing instead of generated,
because six tries each could not make the generator draw them right:

- **ghost-rabbit `idle` 3 and 5, `sleep` 1** (half-closed and heavy eyes).
  Generated half-blinks came out sly, deadpan or rolled. `blink-inbetween.py`
  composites them from the idle sheet's open frame (cell 1) and closed frame
  (cell 4): below the lid line the open eye, above it the closed frame's lid,
  the lid line the closed frame's own arc. Nothing outside the eyes changes.
  The commands are in `source/ghost-rabbit/*_built.txt`; run on `idle.png`
  they give the same pixels as the two built sheets (checked 2026-11-10).
- **leaf-pangolin `idle` 2** (the breath). `creature-cut.py` stretches frame 1
  upwards by 1 percent with the feet staying put (`{"of": 1, "taller": 1.01}`
  in the table): the top of the head rises about 2 px in the strip and 1 px on
  screen, as the panda's and the axolotl's drawn breaths do. The penguin's
  own breath lifts its chest 2 px and its head 1 px in the strip; 1.5 percent,
  the figure first proposed, would lift the sprout about 3.5 px, more than any
  companion breathes. The app never shows this frame as it plays `idle` today
  (it holds frame 1 and blinks through 3, 4, 5).

### How a sheet becomes a strip

`python tools/creature-cut.py <sheets-dir>` (add `--only ghost-rabbit` or
`--only ghost-rabbit/idle` for a part, `--cache <dir>` to keep the keyed
sheets between runs, `--debug <dir>` for pictures of the aligned frames with
the floor line and anchor drawn in). Needs Pillow and numpy. Then
`python tools/creature-qc.py`.

1. **Key.** The key colour is measured from each sheet's border (the green
   differs by a few levels from sheet to sheet; the pangolin's is magenta).
   `spritefix.chroma_key` then sorts every pixel into background, paint or a
   blend of the two. Paint keeps its colour and is opaque. A blend beside
   paint, on the line between the key and that paint, is an anti-aliased edge:
   it gets the paint's colour and the alpha the line gives. Any other blend is
   light over the key (a glow, mist, a sparkle, the fairy's ribbon): it gets
   the least alpha it can have and its colour unmixed from the key, so a glow
   stays soft and carries no green. A glow is never cut off at a threshold:
   its faintest tenth fades out, and so does what is only the sheet's
   background wavering (faint light in the key's own colour, or with none of
   the red a green key lacks). Cyan wings and gold stars are paint and are not
   touched; only the key's own hue is taken out of edge pixels (hue 80 to 170
   on green, never above 170), once after keying and once after scaling.
2. **Cut** the grid and take the frames the table lists.
3. **Line up.** Every frame is moved so the animation's anchor stays put,
   left to right and, for frames that stand, top to bottom. The anchor is what
   the creature keeps still in that animation: the best overlap of its body
   for standing poses, a belly or chest mark or the moon charm for hops and
   bounces, the feet for a turn, the middle of the body for a walk, the cut
   line for `peek`. Frames in the air go with their row of the sheet, so a hop
   keeps its height. The ghost rabbit has no feet: its floor line is the tip
   of its tail, and its float cycle and hop are kept as drawn.
4. **Box and scale.** All frames of an animation share one box, whose bottom
   edge is a fixed distance under the floor line (1.5 px on screen, as under
   the penguin's feet; 9.5 px under the ghost rabbit, which floats), scaled
   to 240 px with colour weighted by alpha. Loose pieces under 12 px that are
   faint, or far from the creature in an animation without loose effects, are
   dropped.
5. **Manifest.** As the penguin's, plus `anchor`: the x in the strip that the
   app pins to the floor spot (the first frame's feet; the body's middle for
   the ghost rabbit). The penguin's manifest has none and the app measures
   its feet as before.

**Size.** Each creature is drawn so its idle frame stands as tall as the
penguin's (115.5 px at the default size; the ghost rabbit reaches the same
height floating): `screen_px` in the table is screen pixels per sheet pixel.
**Scale.** The sheets were not all drawn at one size (side views are smaller,
`peek` is larger). Each animation's `scale` was set so its head matches the
idle strip's on screen: `creature-qc.py` slides idle's head over the frame at
a range of sizes and takes the best match, and the sheet agents' own
measurements (eye distance, ear and orb spacing, body area) agree with it to
a few percent. The manifest's `scale` is that times the box height.

### What the QC measures

`creature-qc.py` prints one row per strip and exits 1 on any failure. Limits
are in screen pixels at the default size (120), not strip pixels.

| Check | What is measured | Limit |
| ----- | ---------------- | ----- |
| size | strip is frames x w by h as the manifest says; all twelve are there, with the penguin's frame counts and rates | exact |
| fringe | edge pixels (alpha above 32, within 2 px of one that isn't) within 100 RGB levels of the key, or of the key's hue and tinted more than 10 levels its way | 0 |
| x | spread of the animation's anchor, left to right, over the frames | 1 px |
| y | spread of the floor line over the frames that stand on it | 1 px |
| head | head size on screen against idle's (best-match size, as above) | 3 percent |
| border | pixels with alpha above 32 on a frame's outermost rows and columns | 0 |
| specks | loose pieces under 12 px, over 6 px from the creature, that are faint or in an animation without loose effects | 0 |

Results on 2026-11-10 (all 48 strips pass; worst value per creature, and the
animation it is in):

| Creature | fringe | x, px | y, px | head, % | border | specks | loose pieces meant |
| -------- | -----: | ----- | ----- | ------- | -----: | -----: | -----------------: |
| fire-red-panda | 0 | 0.47 (think) | 0.26 (walk) | -1.1 (sleep) | 0 | 0 | 112 |
| ghost-rabbit | 0 | 0.49 (wave) | 0.60 (think) | -0.8 (peek) | 0 | 0 | 48 |
| leaf-pangolin | 0 | 0.53 (turn) | 0.26 (talk) | -0.9 (peek) | 0 | 0 | 108 |
| fairy-axolotl | 0 | 0.51 (peek) | 0.35 (walk) | -0.8 (wave) | 0 | 0 | 135 |

The head sizes are near zero because the scales were set with this same
measurement; what stands behind them is the comparison with the sheet agents'
independent figures. Most agree within 2 percent. The ones that differ more:
the panda's `think` (0.974 here; 1.04 was suggested from the ear spacing,
which a tilted head throws off), the rabbit's `peek` (0.881; 0.83 from the ear
orbs, while the distance between the eyes also says about 0.89), the
axolotl's `walk`, `beam` and `peek` (1.222, 1.173 and 1.035; 1.198, 1.14 and
1.0 from body area), and the pangolin's `walk`, which came with no figure
(1.226: it is drawn in 384 px cells).

What it cannot tell: whether the motion reads well or a frame is on-model (the
owner watches the previews for that), and whether a loose piece it counts as
meant is a sparkle or a blemish (the `loose` column is for the eye). `x` uses
the anchor the cutter lined the frames up by (or the `check` the table names,
where the frames were kept as drawn), so it shows the strip kept that
alignment through scaling, not that the anchor was the right choice. `y` is
not judged where the table keeps frames as drawn (the ghost rabbit's float
cycle and hop).

Known and accepted:

- In `alert` three creatures stand a little higher than in their other
  animations, because the glow reaches under the feet and nothing may be
  clipped: the fire red panda 1.1 px, the fairy axolotl 0.9 px, and
  the leaf pangolin 3 px (it stands on its lime band).
- The fire red panda's `sleep` lines its lying frames up with the standing
  ones by the muzzle, so it lies down where it stood.
- `peek` strips are 240 px tall for about 40 px on screen, like the penguin's,
  so they are the largest files.
- Pale effects (the axolotl's sparkles, the rabbit's mist and orbs) are faint
  on a light taskbar. The penguin's `charge` got a dark halo for that in its
  touch-up; nothing of the kind was added here, because these strips are cut
  from the approved sheets and not retouched.
- The ghost rabbit's moon charm sways about 1 px on screen in `alert` while
  its body stays put: the frames are lined up by the body.

## Still to do

- 2× strips (480 px) for high-density displays, only needed if someone sets
  the size above 120 at 200% display scaling: regenerate from the sheets with
  the same slicer, or re-prompt at a larger size if 2× upscaling blurs.
- A left-facing `walk` is the mirrored strip; check that the lightning bolts
  and the belly mark read correctly when mirrored, or draw a left sheet.
- A high-contrast outline variant and a reduced-motion still for each pose.
- Copy the 2026-11-09 `beam` sheet into the raw-sheet archive next to the
  others.
