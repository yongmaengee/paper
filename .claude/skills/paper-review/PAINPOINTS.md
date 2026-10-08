# Pain points log (pi0 first pass → what the tooling now does about each)

| # | Symptom | Cause | Fix / rule |
|---|---|---|---|
| 1 | Screenshots of figures are blurry/heavy and need manual cropping | Raster capture | `extract_figures.py` re-renders the PDF region at 200 dpi (vector stays sharp), located from the `Fig. N:` caption block |
| 2 | First crop of Fig. 6/7 included neighbouring column text and blank top margin | Column test used bbox overlap (gutter overlap) and invisible white background rectangles counted as graphics | Column membership by bbox **centre**; skip white-filled/no-stroke drawings; `autocrop()` trims white margins. Still **eyeball every PNG** — heuristic can fail on full-width/side-by-side figures → use `--override '{"N":[x0,y0,x1,y1,page]}'` |
| 3 | Page text for pages with figures was glyph soup (`G.G 0%G)Z)0./GSO`) and polluted the extraction | Figure labels are outlined/Type3 glyphs with garbage Unicode in the text layer | `outline.py --figures figures.json` drops text blocks inside figure bboxes and blocks with < 75% sane characters |
| 4 | `pdftotext -layout` interleaves two columns (unreadable) | Two-column IEEE-style layout | `outline.py` orders blocks: full-width blocks, then left column, then right column |
| 5 | Heading detection returned axis labels ("1 5 10 Fine-Tuning Data (Hours)") as sections | Regex on numbers/letters matches chart text | Same garbage/figure filter + require 4+ letters; headings still only a *hint* — confirm the Appendix boundary by page |
| 6 | Appendix figures (e.g. Fig. 14) got extracted | No page limit | `--max-page` = last body page (Appendix starts p.15 for pi0 → 14) |
| 7 | Math: inline `A_t^τ` written as plain text rendered raw in HTML | Authoring slip — only `$$…$$` blocks were LaTeX | Rule: every symbol with sub/superscript goes in `$…$`; check the rendered HTML, not just the md |
| 8 | markdown-it-py `add_render_rule` lambdas crashed (`takes 4 positional arguments but 5 were given`) | Rules are bound as methods → leading `self` | Rule signature is `(self, tokens, idx, options, env)` |
| 9 | Extracted text lost sub/superscripts and equation structure (`Aτ t`) | PDF text layer | Re-derive equations from the rendered page image when it matters; don't trust extracted math |
| 10 | arXiv `file` reports wrong page count (8 vs 17) | `file(1)` heuristic | Use `pdfinfo`; `paper.sh fetch` prints title/pages for sanity |
| 11 | pi0.5 Fig. 7 silently missing (only a `[warn]` on stderr that `paper.sh` hid) | Figure has sub-captions `(a) … (b) …` (3 wide lines) that were taken for a body paragraph, blocking the region above | `(a)/(b)` blocks are sub-captions: not barriers, always included in the crop. `paper.sh prep` now shows warnings |
| 12 | Fig. 7 crop swallowed the neighbouring Fig. 6 | Nothing stopped the upward search except body paragraphs | Other `Fig. N:` captions are barriers too |
| 13 | pi0.5 Fig. 3 (model overview) cropped to its bottom strip only | A diagram label `pre-trained VLM … pre-trained VLA` is 3 lines × wide → counted as a body paragraph | Body paragraph additionally needs ≥ 120 chars |
| 14 | Fig. 1 crop had a sliver of the caption's first line | +3 pt padding crossed the caption edge | Clamp the crop to the caption edge |
| 15 | Scaffold put figures in the wrong section (Fig. 3 under Related Work, Fig. 5 under Pre-training) | PDF floats figures to page tops | `scaffold.py` places by first citation in running text; still check by hand (pi0.5 Fig. 7 was first cited in a passing remark in §IV-C, Fig. 2 never cited) |
| 16 | Lint false positives: paper title in H1, section titles, task-name lists flagged as copied | 8-gram match is blind to titles/lists | Exempt H1/headings, quoted `"labels"`, and runs with < 2 function words. Mutation test (`/tmp` copy with a pasted sentence, removed section, TODO, plain-text math, dropped figure) confirms the lint still fires |
| 17 | Page text with equations: Eq. (1) came out as shredded fragments | PDF text layer | Render the region and read it (done for pi0.5 Eq. 1); don't trust extracted math |
| 18 | Shell output sometimes showed nothing for non-empty text files | Display quirk with `grep -v '^$' … | cut` on long single-line paragraphs | Use the Read tool for per-page text |

