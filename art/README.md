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
[`../penguin_companion/anim/`](../penguin_companion/anim), where the app loads
them; paths below are relative to this folder.

## Files

| Path                         | What it is                                                                                                        |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `source/reference-sheet.jpg` | The owner's character sheet (front, side, jump, charge, beam and angry poses), as supplied on 2026-10-05.         |
| `../penguin_companion/anim/<name>.png` | One horizontal strip per animation, 240 px tall, frames left to right, transparent background. |
| `../penguin_companion/anim/manifest.json` | Per animation: `frames`, the frame width `w` and height `h` in pixels, the playback rate `fps`, `loop`, the display `scale`, and `touchup` once `penguin-touchup.py` has fixed the strip. |
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

The app plays some strips in its own order (`../penguin_companion/behavior.py`):
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
   animation, and wrote the strips at 240 px into `../penguin_companion/anim/`.
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

## Still to do

- 2× strips (480 px) for high-density displays, only needed if someone sets
  the size above 120 at 200% display scaling: regenerate from the sheets with
  the same slicer, or re-prompt at a larger size if 2× upscaling blurs.
- A left-facing `walk` is the mirrored strip; check that the lightning bolts
  and the belly mark read correctly when mirrored, or draw a left sheet.
- A high-contrast outline variant and a reduced-motion still for each pose.
- Copy the 2026-11-09 `beam` sheet into the raw-sheet archive next to the
  others.
