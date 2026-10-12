#!/usr/bin/env python3
"""Generate the skeleton of <slug>_ko.md from outline + figures.

Mirrors the structure of the pi0 review: header (source/scope/convention) -> 0. 한 줄 요약 -> Abstract
-> one section per body heading (same numbering as the paper) with each figure placed under the
heading that precedes it on the page -> 읽기 체크리스트 built from the appendix headings.
Every spot the author must fill carries a `TODO` marker; lint_review.py fails while any TODO remains.

  scaffold.py <slug> [--docs DIR] [--force]
Needs: docs/papers/<slug>.pdf, docs/<slug>/figures/figures.json (run `paper.sh prep <slug> <max_page>` first).
"""
import argparse, json, os, re, subprocess, sys, tempfile
import pymupdf

STOP = re.compile(r"^(appendix|references|acknowledg)", re.I)
OK_HEAD = re.compile(r"^(?:[IVX]+\.|[A-Z]\.|\d+(?:\.\d+)*\.?)\s+[A-Z]")  # "1 Introduction", "4.1 Title", "II. TITLE"


def all_headings(pdf):
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        subprocess.run([sys.executable, os.path.join(here, "outline.py"), pdf, "--json", f.name],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.load(open(f.name))


def headings(pdf):
    allh = all_headings(pdf)
    body, appendix, in_app = [], [], False
    for h in allh:
        if STOP.match(h["title"]):
            in_app = in_app or h["title"].lower().startswith("appendix")
            if not in_app:
                continue
        if not (OK_HEAD.match(h["title"]) or STOP.match(h["title"])):
            continue
        if in_app:
            if not STOP.match(h["title"]): appendix.append(h)
        elif not STOP.match(h["title"]):
            body.append(h)
    return body, appendix


def first_mentions(doc, body, last_page):
    """{fig_no: index of the body heading under which the figure is first referenced in running text}.
    Figures float in the PDF, so physical position is a poor guide; the section that first cites them is better."""
    from outline import page_blocks, garbage
    norm = lambda t: re.sub(r"\W+", "", t.lower())
    heads = [norm(h["title"]) for h in body]
    cur, found = -1, {}
    for pno in range(1, last_page + 1):
        for b in page_blocks(doc[pno - 1]):
            t = " ".join(b[4].split())
            if garbage(t): continue
            nt = norm(t)
            if len(t) < 90 and nt in heads:
                cur = heads.index(nt); continue
            if re.match(r"^\s*(?:Fig\.|Figure)\s*\d+\s*[:.]", t): continue   # captions don't count
            for m in re.finditer(r"\b(?:Fig\.|Figure)\s*(\d+)", t):
                found.setdefault(m.group(1), cur)
    return found


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--docs"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    docs = a.docs or os.path.join(os.path.dirname(__file__), "../../../../docs")
    docs = os.path.abspath(docs)
    pdf = f"{docs}/papers/{a.slug}.pdf"; out = f"{docs}/{a.slug}/{a.slug}_ko.md"
    if os.path.exists(out) and not a.force:
        sys.exit(f"{out} exists (use --force to overwrite)")
    figs = json.load(open(f"{docs}/{a.slug}/figures/figures.json"))
    doc = pymupdf.open(pdf)
    first = doc[0].get_text()
    arx = re.search(r"arXiv:(\d{4}\.\d{4,5}v\d+)", first)
    title = " ".join((doc.metadata.get("title") or "").split()) or " ".join(first.split("\n")[:2])
    body, appendix = headings(pdf)
    last_body_page = max(m["page"] for m in figs.values())

    def label_level(t):  # top level (roman "II." / "1 Title") -> ##; sub level ("A." / "2.1 Title") -> ###
        m = re.match(r"^(\d+(?:\.\d+)*)\.?\s", t)
        if m: return "##" if "." not in m.group(1) else "###"
        return "##" if re.match(r"^[IVX]+\.", t) else "###"

    placed = {n: False for n in figs}
    first = first_mentions(doc, body, last_body_page)
    def figs_for(idx):
        """figures whose first citation is under body[idx] (idx=-1: before the first heading); page-1 teaser stays on top"""
        res = []
        for n, m in sorted(figs.items(), key=lambda kv: int(kv[0])):
            if placed[n]: continue
            at = -1 if m["page"] == 1 else first.get(n)
            if at is None: continue
            if at == idx: res.append(n); placed[n] = True
        return res

    def fig_md(n):
        cap = " ".join(figs[n]["caption"].split())
        return (f"![Fig. {n}](figures/fig_{n}.png)\n*Fig. {n}. TODO 캡션 한국어 (p.{figs[n]['page']})*\n"
                f"<!-- 원문 캡션: {cap} -->\n")

    L = [f"# {title} — 한국어 리뷰 노트\n",
         f"- 원문: TODO 저자/기관, arXiv:{arx.group(1) if arx else 'TODO'} · [PDF](../papers/{a.slug}.pdf)",
         f"- 범위: 본문(Abstract ~ {body[-1]['title'] if body else 'TODO'}). **Appendix와 References는 제외.** 부록에만 있는 내용은 \"→ App. X\"로 위치만 표시.",
         "- 형식: 문장 단위 번역이 아니라 **섹션별 내용을 한국어로 재구성한 노트**. 수치·수식·실험 설정은 원문 기준, 논문의 주장과 내 코멘트는 `> 리뷰어 메모`로 구분.",
         "- Figure는 PDF에서 벡터 영역을 그대로 잘라낸 것 (`figures/fig_N.png`, 생성: `extract_figures.py`).\n", "---\n",
         "## 0. 한 줄 요약\n\nTODO\n"]
    for n in figs_for(-1): L.append(fig_md(n))
    L.append("## Abstract\n\n- TODO\n")
    for i, h in enumerate(body):
        L.append(f"{label_level(h['title'])} {h['title']}  <!-- p.{h['page']} -->\n\n- TODO\n")
        for n in figs_for(i): L.append(fig_md(n))
    for n in [k for k, v in placed.items() if not v]: L.append(fig_md(n))  # never cited in body text -> end, author decides
    L.append("---\n\n## 부록: 읽기 체크리스트 (후속 리뷰용)\n")
    for h in appendix: L.append(f"- [ ] App. {h['title']}: TODO 왜 볼 가치가 있는지")
    L.append("- [ ] 데이터/체크포인트 공개 범위와 재현성\n")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(out, f"| {len(body)} body sections, {len(figs)} figures, {len(appendix)} appendix headings, body ends p.{last_body_page}")


if __name__ == "__main__":
    main()
