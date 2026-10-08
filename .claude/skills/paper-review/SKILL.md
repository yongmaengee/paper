---
name: paper-review
description: Fetch an arXiv robotics/ML paper, extract its figures as crisp PNG crops, map sections (body vs appendix), write a Korean section-by-section review note in markdown with figures and LaTeX, and render it to standalone HTML. Use when the user asks to review/translate/summarize a paper into docs/<slug>/.
---

# paper-review

Layout. Tools/skills live in the workspace (committed). `docs/` (a symlink to `~/Desktop/paper/docs`) holds **only results and reference PDFs**;
intermediates go to `<repo>/.cache/` (git-ignored):

```
docs/papers/<slug>.pdf            original PDF
docs/<slug>/figures/fig_N.png     cropped figures + figures.json (page, bbox, caption)
docs/<slug>/<slug>_ko.md          the review note (figures embedded as relative paths)
docs/<slug>/<slug>_ko.html        rendered (KaTeX, TOC sidebar); --embed makes a single shareable file

.cache/<slug>/text/pNN.txt        (workspace, git-ignored) column-ordered text per page, figure glyph noise removed
```

## Workflow

1. `scripts/paper.sh fetch <arxiv_id> <slug>` — check the printed title/pages match the intended paper.
2. `scripts/paper.sh prep <slug>` — prints the section map. Find the page where the Appendix starts; then
   `scripts/paper.sh prep <slug> <last_body_page>` to extract figures and text.
3. **Look at every `figures/fig_N.png`** (Read tool). Fix bad crops with
   `extract_figures.py ... --override '{"N":[x0,y0,x1,y1,page]}'` (PDF points, 1-indexed page). See `PAINPOINTS.md` #2.
4. `scripts/paper.sh scaffold <slug>` — generates `<slug>_ko.md` (header, 0. 한 줄 요약, Abstract, one heading per paper section, figures placed under the section that first cites them, 읽기 체크리스트 from the appendix headings), all with `TODO` markers.
   Figures float, so **move any misplaced figure** by hand (e.g. a figure first cited in a passing remark, or never cited).
5. Read `.cache/<slug>/text/pNN.txt` for the body pages only (skip Appendix and References unless asked). When an equation matters, render that page region
   (`page.get_pixmap(dpi=170, clip=Rect(...))`) and read it — extracted math is shredded. Then fill in `<slug>_ko.md`:
   - Header: source, scope (what was excluded), and the convention that `> 리뷰어 메모` blocks are the reviewer's comments, not the paper's.
   - One `##` per paper section, same numbering as the paper, `![Fig. N](figures/fig_N.png)` + italic Korean caption where the figure is first discussed.
   - Content is a Korean **restatement of the section in the writer's own words** (claims, numbers, equations, setups) — not a sentence-by-sentence reproduction. Keep numbers and equations faithful to the paper; point to `→ App. X` for appendix-only details.
   - All math in `$…$` / `$$…$$` — including sub/superscripts inside bullets and captions.
   - Add critical notes (confounders, missing error bars, baseline fairness) as `> 리뷰어 메모`, and flag any values read off a plot by eye as approximate.
6. `scripts/paper.sh lint <slug>` until it prints `0 error(s)`. It rejects leftover TODO, extracted-but-unused/out-of-order/uncaptioned figures,
   missing paper sections, plain-text math, and any 8+ word English run copied from the paper (headings and "quoted labels" are exempt).
7. `scripts/paper.sh html <slug>` and look at the result (headless Chrome screenshot:
   `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --virtual-time-budget=10000 --window-size=1300,16000 --screenshot=/tmp/x.png file://…/<slug>_ko.html`, then crop with PIL to inspect math/figures).
8. Append new pain points to `PAINPOINTS.md`.

## Tools

| script | purpose |
|---|---|
| `scripts/paper.sh` | fetch / prep / html wrapper (creates `.venv` from `requirements.txt` if missing) |
| `scripts/extract_figures.py` | caption-anchored figure crops, 200 dpi, autocrop, `--max-page`, `--override`, `--caption-above` |
| `scripts/outline.py` | section map, column-ordered per-page text, `--figures` noise filter, `--json` headings with page/y |
| `scripts/scaffold.py` | note skeleton mirroring the pi0 review structure |
| `scripts/lint_review.py` | quality gate for the note (see workflow step 6) |
| `scripts/md2html.py` | md → standalone HTML (KaTeX CDN or `--katex-local`, mermaid fences, `--embed` base64 images) |

## Gotchas

- Headings from `outline.py` are hints; confirm the Appendix boundary by page.
- Extracted math loses structure; re-derive from the rendered page when it matters.
- Papers with captions above figures need `--caption-above`; a few figures (full-width next to a column caption) need `--override`.
- KaTeX/mermaid load from a CDN: offline viewing needs `--katex-local`.
- Paper PDFs are third-party copyrighted works: keep them in `docs/` (git-ignored), don't commit or redistribute them or long verbatim passages.
