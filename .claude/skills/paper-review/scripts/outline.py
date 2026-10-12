#!/usr/bin/env python3
"""Print a section/page map of a paper PDF and find where the main body ends.

Headings are detected from the font-size / bold / small-caps-style patterns common in arXiv
papers (roman-numeral or numbered headings, 'References', 'Appendix'). Use the output to decide
--max-page for extract_figures.py and to split the PDF text per section for translation/review.
Also dumps column-ordered text per page (`--text DIR`) since pdftotext -layout interleaves columns.
"""
import argparse, os, re
import pymupdf

# numbered headings in roman / letter / decimal style, with or without trailing dot ("1 Introduction", "4.1 Title", "II. RELATED WORK", "A. Foo")
HEAD = re.compile(r"^(?:[IVX]+\.|[A-Z]\.|\d+(?:\.\d+)*\.?)\s+[A-Z]|^(?:references|appendix|acknowledg|contributions|abstract)", re.I)


def body_font_size(doc):
    """Most common span size (by characters) = body text size."""
    import collections
    c = collections.Counter()
    for p in doc:
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    c[round(s["size"], 1)] += len(s["text"])
    return c.most_common(1)[0][0] if c else 10.0


def block_sizes(page):
    """{(x0,y0) rounded: (max span size, #lines)} to look up a heading candidate's font size."""
    out = {}
    for b in page.get_text("dict")["blocks"]:
        if b["type"] == 0 and b["lines"]:
            out[(round(b["bbox"][0]), round(b["bbox"][1]))] = (max(s["size"] for l in b["lines"] for s in l["spans"]), len(b["lines"]))
    return out


def page_blocks(page):
    """Blocks in reading order: full-width first by y, then left column, then right column."""
    pw = page.rect.width
    bl = [b for b in page.get_text("blocks") if b[6] == 0]
    def key(b):
        full = (b[2] - b[0]) > 0.6 * pw
        col = 0 if full else (1 if b[0] < pw / 2 - 10 else 2)
        return col, b[1]
    # keep full-width blocks in y-order but split column text around them
    full = sorted([b for b in bl if (b[2] - b[0]) > 0.6 * pw], key=lambda b: b[1])
    cols = [b for b in bl if b not in full]
    out, y0 = [], -1
    for f in full + [(0, 1e9, 0, 1e9, "", 0, 0)]:
        seg = [b for b in cols if y0 <= b[1] < f[1]]
        out += sorted([b for b in seg if b[0] < pw / 2 - 10], key=lambda b: b[1])
        out += sorted([b for b in seg if b[0] >= pw / 2 - 10], key=lambda b: b[1])
        if f[1] < 1e9: out.append(f)
        y0 = f[1]
    return out


def load_fig_boxes(path):
    """figures.json from extract_figures.py -> {page: [Rect]} so text baked into figures can be dropped."""
    import json
    boxes = {}
    for m in json.load(open(path)).values():
        boxes.setdefault(m["page"], []).append(pymupdf.Rect(m["bbox"]))
    return boxes


def garbage(t):
    """Glyph soup from figures whose labels were outlined/Type3-encoded: very low share of letters/digits/spaces."""
    ok = sum(c.isalnum() or c in " .,;:()-'\"" for c in t)
    return len(t) > 6 and ok / len(t) < 0.75


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pdf"); ap.add_argument("--text", help="dump per-page text here")
    ap.add_argument("--figures", help="figures.json: drop text blocks inside figure bboxes")
    ap.add_argument("--json", help="write headings [{page,y,title}] here (used by scaffold.py)")
    a = ap.parse_args()
    fb = load_fig_boxes(a.figures) if a.figures else {}
    doc = pymupdf.open(a.pdf)
    if a.text: os.makedirs(a.text, exist_ok=True)
    heads = []
    body_size = body_font_size(doc)
    for pno, page in enumerate(doc, 1):
        lines = []
        sizes = block_sizes(page)
        for b in page_blocks(page):
            t = " ".join(b[4].split())
            r = pymupdf.Rect(b[:4])
            if any((r & f).get_area() > 0.5 * r.get_area() for f in fb.get(pno, [])) or garbage(t):
                continue
            lines.append(t)
            sz, nl = sizes.get((round(b[0]), round(b[1])), (body_size, 1))
            # headings are at least body-sized (figure labels/list items inside figures are smaller) and at most 2 lines
            if len(t) < 90 and HEAD.match(t) and not t.startswith("Fig") and not garbage(t) and re.search(r"[A-Za-z]{4}", t) \
                    and sz >= body_size * 0.95 and nl <= 2:
                print(f"p{pno:>2}  {t}")
                heads.append({"page": pno, "y": round(b[1], 1), "title": t})
        if a.text:
            open(os.path.join(a.text, f"p{pno:02d}.txt"), "w").write("\n\n".join(lines))
    if a.json:
        import json; json.dump(heads, open(a.json, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
