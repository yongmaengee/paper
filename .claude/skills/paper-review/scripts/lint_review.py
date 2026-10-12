#!/usr/bin/env python3
"""Lint a review note against its source. Encodes every mistake from the pi0 pass (see PAINPOINTS.md).

  lint_review.py docs/<slug>/<slug>_ko.md        (expects docs/papers/<slug>.pdf + docs/<slug>/figures/figures.json)

ERROR (exit 1): TODO left; figure missing/unused/uncaptioned; image file missing;
                body section from the PDF has no matching heading; plain-text math (sub/superscripts outside $..$);
                8+ word English run copied from the paper (note must be in the writer's own words);
                header lacks source/scope/convention.
WARN:           figures not in numeric order; numbers absent from the paper; thin note / empty leaf sections; no `> 리뷰어 메모`; figure values read by eye not flagged as approximate; table/section is very short.
"""
import json, os, re, subprocess, sys
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scaffold import headings, all_headings as headings_all  # noqa: E402


def strip_code_math(t):
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"\$\$.*?\$\$", " ", t, flags=re.S)
    t = re.sub(r"\$[^$\n]+\$", " ", t)
    t = re.sub(r"`[^`\n]*`", " ", t)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)       # scaffold keeps source captions in comments
    t = re.sub(r"!?\[[^\]]*\]\([^)]*\)", " ", t)       # links / images
    t = re.sub(r"https?://\S+", " ", t)
    return t


def words(t):
    return re.findall(r"[a-z0-9][a-z0-9\-']*", t.lower())


def main():
    md_path = sys.argv[1]; slug = os.path.basename(md_path).rsplit("_ko", 1)[0]
    docs = os.path.dirname(os.path.dirname(os.path.abspath(md_path)))
    pdf = f"{docs}/papers/{slug}.pdf"; fj = f"{docs}/{slug}/figures/figures.json"
    src = open(md_path, encoding="utf-8").read()
    errs, warns = [], []
    E = lambda m: errs.append(m); W = lambda m: warns.append(m)

    for i, l in enumerate(src.split("\n"), 1):
        if "TODO" in l: E(f"L{i}: TODO left: {l.strip()[:70]}")

    head = src.split("\n---", 1)[0]
    for key, why in (("원문", "source"), ("범위", "scope (appendix excluded)"), ("리뷰어 메모", "reviewer-note convention")):
        if key not in head: E(f"header lacks {why} ('{key}')")
    if "> 리뷰어 메모" not in src: W("no '> 리뷰어 메모' blocks: add critical notes (confounders, error bars, fairness)")

    # figures
    figs = json.load(open(fj)) if os.path.exists(fj) else {}
    refs = re.findall(r"!\[[^\]]*\]\((figures/fig_(\d+)\.png)\)", src)
    seen = [int(n) for _, n in refs]
    for path, n in refs:
        if not os.path.exists(f"{docs}/{slug}/{path}"): E(f"image missing: {path}")
    for n in figs:
        if int(n) not in seen: E(f"Fig. {n} extracted but not embedded")
    for n in set(seen):
        if str(n) not in figs: E(f"Fig. {n} embedded but not in figures.json")
    if seen != sorted(seen): W(f"figures embedded out of numeric order {seen} (fine if the paper cites them in that order)")
    for n in seen:
        if not re.search(rf"!\[Fig\. {n}\]\(figures/fig_{n}\.png\)\n\*Fig\. {n}\.", src): E(f"Fig. {n}: missing italic caption line right below the image")

    # section coverage (same numbering/title as the paper)
    if os.path.exists(pdf):
        body, _ = headings(pdf)
        if len(body) < 3: E(f"heading detection found only {len(body)} body section(s): outline is unreliable, check `outline.py` output by hand")
        mdheads = [re.sub(r"\s*<!--.*?-->", "", h).strip().lower() for h in re.findall(r"^#{2,3} (.+)$", src, flags=re.M)]
        norm = lambda s: re.sub(r"[^a-z0-9π가-힣 ]", "", s.lower()).strip()
        for h in body:
            t = norm(re.sub(r"^(?:[IVX]+\.|[A-Z]\.|\d+(?:\.\d+)*\.)\s+", "", h["title"]))
            if not any(t[:25] in norm(m) for m in mdheads): E(f"paper section missing from note: '{h['title']}' (p.{h['page']})")

    # depth: a note far shorter than the paper body is a stub even if every heading exists
    if os.path.exists(pdf) and body:
        d = pymupdf.open(pdf)
        end = min([h["page"] for h in headings_all(pdf) if re.match(r"(references|acknowledg|appendix)", h["title"], re.I)] or [len(d)])
        body_chars = sum(len(d[i].get_text()) for i in range(end))
        note_chars = len(re.sub(r"\s+", "", strip_code_math(src)))
        if note_chars < 0.12 * body_chars: W(f"note looks thin: {note_chars} chars vs ~{body_chars} body chars of the paper ({100*note_chars//max(body_chars,1)}%; pi0/pi0.5 notes are ~25-40%)")
        # leaf sections only: a parent heading that is directly followed by its sub-sections is fine
        nh = [(len(m.group(1)), m.group(2), m.end()) for m in re.finditer(r"^(#{2,3}) (.+)$", src, flags=re.M)]
        titles = {re.sub(r"\s*<!--.*?-->", "", h["title"]).strip() for h in body}
        for i, (lvl, title, end_) in enumerate(nh):
            title = re.sub(r"\s*<!--.*?-->", "", title).strip()
            if title not in titles: continue
            nxt_lvl, nxt_start = (nh[i + 1][0], nh[i + 1][2] - len(nh[i + 1][1]) - lvl - 1) if i + 1 < len(nh) else (0, len(src))
            if nxt_lvl > lvl: continue
            seg = src[end_:nxt_start]
            if len(re.findall(r"^\s*(?:[-*]|\d+\.)\s", seg, flags=re.M)) + len(re.findall(r"\n\n", seg)) < 2:
                W(f"section '{title}' has almost no content")

    # numbers must exist in the paper (catches unit slips such as 3.3B -> 330억). Korean unit conversions need a manual look.
    if os.path.exists(pdf):
        src_nums = set(re.findall(r"\d+(?:\.\d+)?", " ".join(pg.get_text() for pg in pymupdf.open(pdf))))
        prose2 = re.sub(r"^#{1,6} .*$", " ", strip_code_math(src), flags=re.M)
        prose2 = re.sub(r"\bFig\.? ?\d+|Table \d+|App\. \w+|p\.\d+|v\d+", " ", prose2)
        odd = sorted({n for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", prose2) if n not in src_nums and (len(n) >= 3 or "." in n)})
        if odd: W(f"numbers in the note that never appear in the paper (check units/typos): {', '.join(odd[:15])}")

    # plain-text math
    plain = strip_code_math(re.sub(r"^# .*$", " ", src, count=1, flags=re.M))  # H1 repeats the paper title
    for i, l in enumerate(plain.split("\n"), 1):
        m = re.search(r"[A-Za-zτθεπ]\w*_[{\w]|[A-Za-zτθεπ0-9)]\^[{\w(.]", l)
        if m and not re.search(r"fig_\d|_ko|\.png", l): E(f"plain-text math (wrap in $..$): …{l[max(m.start()-15,0):m.end()+20].strip()}…")

    # verbatim copying (English runs)
    if os.path.exists(pdf):
        sw = []
        for p in pymupdf.open(pdf): sw += words(p.get_text())
        shingles = {" ".join(sw[i:i + 8]) for i in range(len(sw) - 7)}
        # headings mirror the paper's section titles on purpose; quoted labels ("dishes in sink") are names, not prose
        prose_only = re.sub(r'^#{1,6} .*$', " ", plain, flags=re.M)
        prose_only = re.sub(r'"[^"\n]{1,80}"|“[^”\n]{1,80}”', " ", prose_only)
        mw = words(prose_only)
        STOPW = {"the", "of", "and", "is", "to", "a", "in", "that", "we", "for", "are", "with", "on", "by", "this", "it", "as", "can"}
        # prose only: titles / task-name lists / proper-noun runs have < 2 function words
        prose = lambda sh: sum(w in STOPW for w in sh.split()) >= 2
        hits = sorted(h for h in ({" ".join(mw[i:i + 8]) for i in range(len(mw) - 7)} & shingles) if prose(h))
        for h in hits[:5]: E(f"verbatim 8-word run copied from paper: '{h}'")
        if len(hits) > 5: E(f"... and {len(hits) - 5} more verbatim runs")

    if re.search(r"눈대중|육안|읽힌다|읽으면", src) is None and "Fig." in src and re.search(r"약 ?0\.\d", src):
        W("approximate values (약 0.xx) present without noting they were read off the plot")

    for m in errs: print("ERROR", m)
    for m in warns: print("WARN ", m)
    print(f"{len(errs)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
