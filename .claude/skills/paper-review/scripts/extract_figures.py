#!/usr/bin/env python3
"""Crop every `Fig. N:` / `Figure N:` region of a paper PDF to PNG (vector-safe, no screenshots).

Heuristic: find the caption block, then take all graphics (raster images + vector drawings)
and small text (axis labels) located above it in the caption's column (or full width),
stopping at the nearest body-text paragraph. Captions are assumed to sit BELOW figures;
use --caption-above for papers that put them above. Anything the heuristic gets wrong
is fixed with an override: --override '{"6": [x0, y0, x1, y1, page]}' (PDF points, 1-indexed page).

Outputs <out>/fig_<N>.png and <out>/figures.json (page, bbox, caption text).
"""
import argparse, json, re, sys
import pymupdf

CAP_RE = re.compile(r"^\s*(?:Fig\.|Figure)\s*(\d+)\s*[:.]", re.I)


def blocks_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        text = " ".join(s["text"] for l in b["lines"] for s in l["spans"]).strip()
        if text:
            out.append((pymupdf.Rect(b["bbox"]), text, len(b["lines"])))
    return out


def graphics(page):
    rects = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    for d in page.get_drawings():
        # skip invisible white background panels (they inflate the crop with blank space)
        if d.get("fill") in ((1, 1, 1), (1.0, 1.0, 1.0)) and not d.get("color"):
            continue
        if d["rect"].width > 0.5 or d["rect"].height > 0.5:
            rects.append(pymupdf.Rect(d["rect"]))
    return [r for r in rects if r.width > 1 and r.height > 1]


SUB_RE = re.compile(r"^\s*\(?[a-h]\)\s")  # "(a) Example rollouts. ..." sub-figure caption


def is_subcaption(text):
    return bool(SUB_RE.match(text))


def is_body_para(rect, nlines, col_w, text=""):
    # diagram labels can be 3 wide lines too -> also require real paragraph length (>=120 chars)
    return nlines >= 3 and rect.width >= 0.75 * col_w and not is_subcaption(text) and len(text) >= 120


def find_region(page, cap_rect, above=True):
    pw = page.rect.width
    mid = pw / 2
    full = cap_rect.width > 0.6 * pw
    xr = (0, pw) if full else ((0, mid) if cap_rect.x0 < mid - 20 else (mid, pw))
    col_w = (xr[1] - xr[0]) if not full else pw / 2 - 20
    # an item belongs to the column if its centre lies inside it (gutter-safe)
    inx = lambda r: xr[0] <= (r.x0 + r.x1) / 2 <= xr[1]
    blks = blocks_of(page)
    if above:
        lo = 0
        for r, t, n in blks:
            if inx(r) and r.y1 <= cap_rect.y0 + 1 and (is_body_para(r, n, col_w, t) or CAP_RE.match(t)):
                lo = max(lo, r.y1)
        sel = lambda r: lo - 1 <= r.y0 and r.y1 <= cap_rect.y0 + 2
    else:
        hi = page.rect.height
        for r, t, n in blks:
            if inx(r) and r.y0 >= cap_rect.y1 - 1 and (is_body_para(r, n, col_w, t) or CAP_RE.match(t)):
                hi = min(hi, r.y0)
        sel = lambda r: cap_rect.y1 - 2 <= r.y0 and r.y1 <= hi + 1
    items = [g for g in graphics(page) if inx(g) and sel(g)]
    if not items:
        return None
    # axis labels / panel text that fall inside the graphics' vertical span
    u = pymupdf.Rect(items[0])
    for g in items[1:]:
        u |= g
    for r, t, n in blks:
        if not (inx(r) and sel(r)):
            continue
        if is_subcaption(t) or (not is_body_para(r, n, col_w, t) and r.y0 >= u.y0 - 15 and r.y1 <= u.y1 + 15):
            u |= r
    u = u + (-3, -3, 3, 3)
    u.x0 = max(u.x0, xr[0] + 1); u.x1 = min(u.x1, xr[1] - 1)
    # never let the padding swallow the first caption line
    if above: u.y1 = min(u.y1, cap_rect.y0 - 0.5)
    else: u.y0 = max(u.y0, cap_rect.y1 + 0.5)
    return u


def autocrop(path, pad=8, thr=250):
    """Trim near-white margins left over from the bbox heuristic."""
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.subtract(ImageChops.difference(im, bg).convert("L"), Image.new("L", im.size, 255 - thr))
    box = diff.getbbox()
    if box:
        box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, im.width), min(box[3] + pad, im.height))
        im.crop(box).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("out")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--caption-above", action="store_true")
    ap.add_argument("--max-page", type=int, help="ignore pages after this (1-indexed), e.g. skip appendix")
    ap.add_argument("--override", default="{}", help='JSON {"N": [x0,y0,x1,y1,page]}')
    a = ap.parse_args()
    ov = json.loads(a.override)
    doc = pymupdf.open(a.pdf)
    import os; os.makedirs(a.out, exist_ok=True)
    meta, seen = {}, set()
    for pno, page in enumerate(doc, 1):
        if a.max_page and pno > a.max_page:
            break
        for r, text, _ in blocks_of(page):
            m = CAP_RE.match(text)
            if not m or m.group(1) in seen:
                continue
            n = m.group(1); seen.add(n)
            if n in ov:
                x0, y0, x1, y1, pg = ov[n]
                page_, reg, how = doc[pg - 1], pymupdf.Rect(x0, y0, x1, y1), "override"
            else:
                page_, reg, how = page, find_region(page, r, not a.caption_above), "auto"
            if reg is None:
                print(f"[warn] Fig {n} p{pno}: no graphics found; use --override", file=sys.stderr)
                continue
            pix = page_.get_pixmap(clip=reg, dpi=a.dpi)
            fn = f"fig_{n}.png"; path = os.path.join(a.out, fn); pix.save(path)
            autocrop(path)
            meta[n] = {"file": fn, "page": page_.number + 1, "bbox": [round(v, 1) for v in reg],
                       "method": how, "caption": text}
            print(f"Fig {n}: p{page_.number+1} {how} {pix.width}x{pix.height}")
    json.dump(meta, open(os.path.join(a.out, "figures.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
