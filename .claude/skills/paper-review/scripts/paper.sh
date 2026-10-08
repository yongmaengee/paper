#!/usr/bin/env bash
# One-stop wrapper for the paper-review pipeline.
#   paper.sh fetch   <arxiv_id> <slug>          -> $DOCS/papers/<slug>.pdf (+ sanity check of title/pages)
#   paper.sh prep    <slug> [max_body_page]     -> outline, docs figures/ + figures.json, and per-page text in $CACHE/<slug>/text/ (figure glyph noise removed)
#   paper.sh scaffold <slug> [--force]          -> $DOCS/<slug>/<slug>_ko.md skeleton (sections + figures placed by first citation, TODO markers)
#   paper.sh lint    <slug>                     -> checks the note against the PDF (TODO/figures/sections/math/verbatim copy); exit 1 on errors
#   paper.sh html    <slug> [--embed]           -> $DOCS/<slug>/<slug>_ko.html from <slug>_ko.md
# DOCS defaults to <repo>/docs (symlink to ~/Desktop/paper/docs). Python env: <repo>/.venv (see requirements.txt).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../../../.." && pwd)"
# DOCS = results + reference PDFs only; CACHE = intermediates (git-ignored)
DOCS="${DOCS:-$REPO/docs}"; CACHE="${CACHE:-$REPO/.cache}"; PY="${PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { python3 -m venv "$REPO/.venv" && "$REPO/.venv/bin/pip" -q install -r "$HERE/../requirements.txt"; }
cmd="${1:?fetch|prep|scaffold|lint|html}"; shift
case "$cmd" in
  fetch)
    id="$1"; slug="$2"; mkdir -p "$DOCS/papers"
    curl -fsSL -m 180 -o "$DOCS/papers/$slug.pdf" "https://arxiv.org/pdf/$id"
    head -c 4 "$DOCS/papers/$slug.pdf" | grep -q '%PDF' || { echo "not a PDF (rate limit / wrong id?)"; exit 1; }
    pdfinfo "$DOCS/papers/$slug.pdf" 2>/dev/null | egrep 'Title|Pages'; pdftotext -l 1 "$DOCS/papers/$slug.pdf" - 2>/dev/null | head -3 ;;
  prep)
    slug="$1"; maxp="${2:-}"; pdf="$DOCS/papers/$slug.pdf"; out="$DOCS/$slug"; mkdir -p "$out"
    echo "== outline (appendix/references boundary -> choose max_body_page, figures after it are skipped)"
    "$PY" "$HERE/outline.py" "$pdf" 2>/dev/null
    [ -n "$maxp" ] || { echo "re-run: paper.sh prep $slug <last page before Appendix>"; exit 0; }
    "$PY" "$HERE/extract_figures.py" "$pdf" "$out/figures" --max-page "$maxp" 2>/dev/null
    "$PY" "$HERE/outline.py" "$pdf" --figures "$out/figures/figures.json" --text "$CACHE/$slug/text" >/dev/null 2>&1
    echo "text per page: $CACHE/$slug/text/  | review figures/*.png by eye (Read tool) before trusting them" ;;
  scaffold)
    slug="$1"; shift; "$PY" "$HERE/scaffold.py" "$slug" --docs "$DOCS" "$@" 2>/dev/null ;;
  lint)
    slug="$1"; "$PY" "$HERE/lint_review.py" "$DOCS/$slug/${slug}_ko.md" 2>/dev/null ;;
  html)
    slug="$1"; shift; "$PY" "$HERE/md2html.py" "$DOCS/$slug/${slug}_ko.md" "$@" ;;
  *) echo "unknown: $cmd"; exit 2 ;;
esac
