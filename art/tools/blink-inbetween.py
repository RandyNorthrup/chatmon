# ruff: noqa: B023, B905  (kept as it was when it built the frames in use: lid_curve is only called inside the loop that defines it)
"""Build a blink in-between frame by compositing, the way an animator makes one.

Inputs: the OPEN-eye frame and the CLOSED-eye frame of the same idle sheet (already registered to each other) and an
amount (0 = open, 1 = closed, 0.5 = half closed). Output: the in-between frame. Nothing outside the eyes changes.

For each eye (found from the difference between the two frames):
  * below the lid line the eye is the OPEN frame, unchanged (iris, pupil, lower outline, and the highlight if it sits low);
  * above the lid line the eye is filled with the CLOSED frame's lid and face pixels, so shading and colour match;
  * the lid line is the CLOSED frame's own eyelid arc, moved up to the lid height and fitted to the eye's width, so it
    is the creature's own soft curved arc and not a straight bar;
  * the seams are feathered by about a pixel.

usage (frames cut from one sheet):
  python blink-inbetween.py --sheet idle.png --grid 3x2 --open 1 --closed 4 --amount 0.5 --out half.png
  python blink-inbetween.py --sheet idle.png --grid 3x2 --open 1 --closed 4 --amounts 0.55,0.45 --out row.png
usage (two single-frame images):
  python blink-inbetween.py --open-img open.png --closed-img closed.png --amount 0.5 --out half.png
Several amounts give a one-row image, one frame per amount. --debug <png> writes the detected regions for checking.
Prints one JSON line per eye with what it measured (eye box, lid height, covered share, highlight decision).

Needs Pillow and numpy only.
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image, ImageFilter

DIFF_THRESHOLD = 90        # sum of absolute RGB differences that counts as "the eye changed here"
MARGIN = 3                 # px added around each eye region
FEATHER = 0.8              # px, Gaussian radius on the seams
COVER_TOLERANCE = 0.06     # how far the covered share may move from the amount to keep the highlight whole
ARC_OVERHANG = 0           # px the lid line may stick out past the eye outline in total


def _filt(mask, f):
    return np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(f)) > 127


def dilate(mask, r):
    return _filt(mask, ImageFilter.MaxFilter(2 * r + 1)) if r > 0 else mask


def erode(mask, r):
    return _filt(mask, ImageFilter.MinFilter(2 * r + 1)) if r > 0 else mask


def components(mask):
    """4-connected components of a boolean mask, as lists of (y, x) arrays."""
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        out.append(np.array(pts))
    return out


def eye_regions(open_rgb, closed_rgb):
    """Boolean masks, one per eye. An eye is a solid blob of difference between the two frames (the open iris against
    the closed lid); thin differences, such as an outline that moved by a pixel, are ignored. Each region is the
    difference found within a box around that blob (wide enough for the closed arc's ends), padded by MARGIN."""
    d = np.abs(open_rgb.astype(int) - closed_rgb.astype(int)).sum(-1)
    m = d > DIFF_THRESHOLD
    seeds = [c for c in components(erode(m, 3)) if len(c) >= 20]       # only blobs at least 7 px thick survive
    if not seeds:
        return []
    big = max(len(c) for c in seeds)
    H, W = m.shape
    regions = []
    for c in sorted((c for c in seeds if len(c) >= 0.35 * big), key=lambda c: c[:, 1].mean()):
        y0, x0 = c.min(0) - 3
        y1, x1 = c.max(0) + 3                                           # undo the erosion
        w, h = x1 - x0 + 1, y1 - y0 + 1
        box = np.zeros((H, W), bool)
        box[max(0, int(y0 - 0.35 * h)):int(y1 + 0.35 * h) + 1, max(0, int(x0 - 0.6 * w)):int(x1 + 0.6 * w) + 1] = True
        solid = dilate(erode(m, 1), 1) & m                               # drop 1-2 px slivers (an outline that moved)
        r = erode(dilate(solid & box, 4), 3) & box
        # keep only the part connected to the blob
        keep = np.zeros((H, W), bool)
        for comp in components(r):
            cm = np.zeros((H, W), bool)
            cm[comp[:, 0], comp[:, 1]] = True
            if cm[c[:, 0], c[:, 1]].any():
                keep |= cm
        regions.append(dilate(keep, MARGIN))
    # two seeds inside one eye (iris split by a highlight) would give overlapping regions: merge them
    merged = []
    for r in regions:
        for k, q in enumerate(merged):
            if (r & q).sum() > 0.3 * min(r.sum(), q.sum()):
                merged[k] = q | r
                break
        else:
            merged.append(r)
    return merged


def inbetween(open_rgb, closed_rgb, amount=0.5, info=None):
    """Return the in-between frame (uint8 RGB array). open_rgb and closed_rgb: HxWx3 uint8, registered to each other."""
    o = open_rgb.astype(float)
    c = closed_rgb.astype(float)
    H, W = o.shape[:2]
    out = o.copy()
    # the face without any eye drawn: the closed frame with its eyelid arcs taken out by a median filter
    med = np.asarray(Image.fromarray(closed_rgb).filter(ImageFilter.MedianFilter(17))).astype(float)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    for k, region in enumerate(eye_regions(open_rgb, closed_rgb)):
        # open eye: where the open frame departs from the eyeless face
        eye = (np.sqrt(((o - med) ** 2).sum(-1)) > 40) & region
        if not eye.any():
            continue
        eye = max(components(eye), key=len)
        em = np.zeros((H, W), bool)
        em[eye[:, 0], eye[:, 1]] = True
        # closed eyelid arc: where the closed frame departs from the eyeless face, inside this eye's region, and where
        # the open frame does not show the same line (that would be a face or ear outline, not the eyelid)
        dc = np.sqrt(((c - med) ** 2).sum(-1))
        moved = (np.abs(o - c).sum(-1) > 60) | dilate(em, 1)
        cand = (dc > 25) & region & moved
        if not cand.any():
            continue
        best = max(components(dilate(cand, 1)), key=len)
        bm = np.zeros((H, W), bool)
        bm[best[:, 0], best[:, 1]] = True
        dc = dc * dilate(bm, 1) * region
        top = np.percentile(dc[dc > 25], 90) if (dc > 25).any() else 0
        if top <= 25:
            continue
        arc = np.clip((dc - 25) / (top - 25), 0, 1)
        arc_core = arc > 0.8
        arc_colour = (c[arc_core].mean(0) if arc_core.any() else c[arc > 0.3].mean(0))
        skin = np.where(dilate(arc > 0.05, 1)[..., None], med, c)          # closed frame's lid and face, arc removed
        ex0, ex1 = eye[:, 1].min(), eye[:, 1].max()
        ecx = (ex0 + ex1) / 2.0
        mid_cols = em[:, int(ex0 + 0.3 * (ex1 - ex0)):int(ex0 + 0.7 * (ex1 - ex0)) + 1]      # ignore lash ticks at the sides
        rows = np.nonzero(mid_cols.any(1))[0]
        ey0, ey1 = rows.min(), rows.max()
        # arc geometry (closed frame coordinates)
        cols = np.nonzero(arc.sum(0) > 0.5)[0]
        ax0, ax1 = cols.min(), cols.max()
        colsum = arc[:, ax0:ax1 + 1].sum(0)
        yc = (arc[:, ax0:ax1 + 1] * np.arange(H)[:, None]).sum(0) / np.maximum(colsum, 1e-6)
        ok = colsum > 0.5                                   # a broken arc has empty columns: bridge them
        yc = np.interp(np.arange(len(yc)), np.nonzero(ok)[0], yc[ok])
        n = len(yc)
        y_mid = float(yc[int(0.4 * n):int(0.6 * n) + 1].mean())
        y_ends = float(np.concatenate([yc[:max(1, n // 10)], yc[-max(1, n // 10):]]).mean())
        sag = y_mid - y_ends                               # > 0: the arc hangs down in the middle
        mid = colsum[n // 3:n - n // 3]
        thick = float(np.median(mid[mid > 0.5])) if (mid > 0.5).any() else float(np.median(colsum[ok]))
        # highlight: the largest near-white blob inside the open eye
        hl = None
        em_f = erode(dilate(em, 5), 5) | em                                 # the eye with its highlight hole filled in
        white = (open_rgb.min(-1) > 185) & erode(em_f, 1)                  # includes the highlight's soft edge
        if white.any():
            h = max(components(white), key=len)
            if len(h) >= 6:
                hl = h

        def lid_curve(y_lid):
            """Warp the arc so its middle sits at y_lid over this eye; return (alpha layer, lid centre line per column)."""
            y_end = int(round(y_lid - sag))
            band = em[max(ey0, y_end - 1):min(ey1, y_end + 1) + 1]
            cc = np.nonzero(band.any(0))[0]
            width = (cc.max() - cc.min() + 1) if len(cc) else (ex1 - ex0 + 1)
            sx = float(np.clip((width + ARC_OVERHANG) / (ax1 - ax0 + 1), 0.5, 1.3))
            amid = (ax0 + ax1) / 2.0
            a_img = Image.fromarray((arc * 255).astype(np.uint8))
            warped = a_img.transform((W, H), Image.AFFINE, (1 / sx, 0, amid - ecx / sx, 0, 1, -(y_lid - y_mid)),
                                     resample=Image.BILINEAR)
            wa = np.asarray(warped).astype(float) / 255.0
            cols2 = np.nonzero(wa.sum(0) > 0.3)[0]
            line = np.full(W, np.nan)
            for x in cols2:
                line[x] = (wa[:, x] * np.arange(H)).sum() / wa[:, x].sum()
            line[:cols2.min()] = line[cols2.min()]
            line[cols2.max() + 1:] = line[cols2.max()]
            return wa, line, sx

        y_lid = ey0 + amount * (ey1 - ey0)
        decision = "no highlight found"
        if hl is not None:
            wa, line, sx = lid_curve(y_lid)
            rel = hl[:, 0] - line[hl[:, 1]]                 # > 0: below the lid line (visible)
            vis = float((rel > thick / 2).mean())
            if vis >= 0.98:
                decision = "highlight fully visible"
            elif vis <= 0.02:
                decision = "highlight fully covered"
            else:
                span = float(ey1 - ey0)
                down = float(rel.max() + thick / 2 + 1)      # move the lid down this far to cover it all
                up = float(thick / 2 + 1 - rel.min())        # move the lid up this far to show it all
                if vis >= 0.5 and up / span <= COVER_TOLERANCE:
                    y_lid -= up
                    decision = "lid raised %.1f px to keep the highlight whole" % up
                elif down / span <= COVER_TOLERANCE or vis < 0.5:
                    y_lid += min(down, 2 * COVER_TOLERANCE * span)
                    decision = "lid lowered %.1f px to cover the highlight fully" % min(down, 2 * COVER_TOLERANCE * span)
                else:
                    y_lid -= min(up, 2 * COVER_TOLERANCE * span)
                    decision = "lid raised %.1f px to keep the highlight whole" % min(up, 2 * COVER_TOLERANCE * span)
        wa, line, sx = lid_curve(y_lid)
        # above the lid line, inside the eye region: the closed frame's lid and face
        fill_zone = dilate(em_f, 2) | (region & (wa > 0.02))
        above = np.clip(line[None, :] - yy + 0.5, 0, 1) * fill_zone
        if hl is not None and ("covered" in decision or "to cover" in decision):
            # any highlight pixel under or below the lid line would show as a light speck: fill it with the iris colour
            hm = np.zeros((H, W), bool)
            hm[hl[:, 0], hl[:, 1]] = True
            peek = dilate(hm, 2) & (yy > line[None, :] - thick) & em_f   # also what sits under the lid line itself
            if peek.any():
                iris = o[em & ~dilate(hm, 3) & (yy > line[None, :]) & (yy < line[None, :] + thick + 6)]
                if len(iris):
                    out[peek] = np.median(iris, axis=0)
        above = np.asarray(Image.fromarray((above * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(FEATHER))) / 255.0
        above = np.where(fill_zone | dilate(fill_zone, 2), above, 0)[..., None]
        out = out * (1 - above) + skin * above
        lid_a = (wa * dilate(region, 2))[..., None]
        out = out * (1 - lid_a) + arc_colour * lid_a
        if info is not None:
            covered = (y_lid - ey0) / float(ey1 - ey0)
            info.append({"eye": k + 1, "eye_box_ltrb": [int(ex0), int(ey0), int(ex1), int(ey1)],
                         "closed_arc_x": [int(ax0), int(ax1)], "arc_sag_px": round(sag, 1), "arc_thickness_px": round(thick, 1),
                         "arc_width_scale": round(sx, 3), "lid_y_at_centre": round(float(y_lid), 1),
                         "covered_share_of_eye_height": round(float(covered), 3), "highlight": decision,
                         "region_px": int(region.sum())})
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def cell(img, grid, index):
    cols, rows = grid
    w, h = img.width // cols, img.height // rows
    j, i = divmod(index - 1, cols)
    return img.crop((i * w, j * h, (i + 1) * w, (j + 1) * h))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet"); ap.add_argument("--grid", default="3x2")
    ap.add_argument("--open", type=int, default=1, help="cell number of the open-eye frame (1-based, row by row)")
    ap.add_argument("--closed", type=int, default=4, help="cell number of the closed-eye frame")
    ap.add_argument("--open-img"); ap.add_argument("--closed-img")
    ap.add_argument("--amount", type=float, default=0.5)
    ap.add_argument("--amounts", help="comma-separated amounts: the output is one row with a frame per amount")
    ap.add_argument("--out", required=True); ap.add_argument("--debug")
    a = ap.parse_args()
    if a.sheet:
        grid = tuple(int(v) for v in a.grid.lower().split("x"))
        sheet = Image.open(a.sheet).convert("RGB")
        o_img, c_img = cell(sheet, grid, a.open), cell(sheet, grid, a.closed)
    elif a.open_img and a.closed_img:
        o_img, c_img = Image.open(a.open_img).convert("RGB"), Image.open(a.closed_img).convert("RGB")
    else:
        sys.exit("give --sheet (with --open/--closed cell numbers) or --open-img and --closed-img")
    if o_img.size != c_img.size:
        sys.exit("the open and closed frames must be the same size and registered to each other")
    o, c = np.asarray(o_img), np.asarray(c_img)
    amounts = [float(v) for v in a.amounts.split(",")] if a.amounts else [a.amount]
    frames = []
    for am in amounts:
        info = []
        frames.append(Image.fromarray(inbetween(o, c, am, info)))
        if not info:
            sys.exit("no eye regions found: are the two frames registered, and do the eyes differ between them?")
        for e in info:
            print(json.dumps({"amount": am, **e}))
    row = Image.new("RGB", (o_img.width * len(frames), o_img.height))
    for k, f in enumerate(frames):
        row.paste(f, (k * o_img.width, 0))
    row.save(a.out)
    if a.debug:
        dbg = o.copy()
        for r in eye_regions(o, c):
            edge = r & ~erode(r, 1)
            dbg[edge] = (255, 255, 0)
        Image.fromarray(dbg).save(a.debug)
    print("wrote", a.out, row.size)


if __name__ == "__main__":
    main()
