#!/usr/bin/env python3
"""Render a review markdown file to a standalone HTML (KaTeX math, TOC sidebar, figures, tables).

  md2html.py docs/pi0/pi0_ko.md            -> docs/pi0/pi0_ko.html (images referenced relatively)
  md2html.py docs/pi0/pi0_ko.md --embed    -> images inlined as base64 (single shareable file)

Math: $...$ and $$...$$ (KaTeX via CDN auto-render; needs network once, or pass --katex-local DIR).
Extra syntax: ```mermaid fences render with mermaid (CDN).
"""
import argparse, base64, html, mimetypes, os, re
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin

CSS = """
:root{--fg:#1f2328;--mut:#656d76;--bd:#d0d7de;--bg:#fff;--code:#f6f8fa;--acc:#0969da}
@media(prefers-color-scheme:dark){:root{--fg:#e6edf3;--mut:#8d96a0;--bd:#30363d;--bg:#0d1117;--code:#161b22;--acc:#58a6ff}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.75 -apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
nav{position:fixed;top:0;left:0;bottom:0;width:260px;overflow:auto;padding:20px 16px;border-right:1px solid var(--bd);font-size:13px;line-height:1.5}
nav a{display:block;color:var(--mut);text-decoration:none;padding:2px 0}nav a:hover{color:var(--acc)}nav a.h3{padding-left:14px}
main{margin-left:260px;max-width:860px;padding:32px 48px 120px}
h1,h2,h3{line-height:1.3}h2{border-bottom:1px solid var(--bd);padding-bottom:.3em;margin-top:2em}
img{max-width:100%;display:block;margin:1em auto;background:#fff;border-radius:4px}
figure{margin:1.5em 0}figcaption{color:var(--mut);font-size:14px;text-align:center}
table{border-collapse:collapse;margin:1em 0;font-size:14px}td,th{border:1px solid var(--bd);padding:6px 12px}th{background:var(--code)}
code{background:var(--code);padding:.15em .35em;border-radius:4px;font-size:.9em}pre{background:var(--code);padding:14px;border-radius:6px;overflow:auto}pre code{background:none;padding:0}
blockquote{margin:1em 0;padding:.2em 1em;border-left:4px solid var(--bd);color:var(--mut)}
@media(max-width:900px){nav{display:none}main{margin:0;padding:20px}}
"""


def slug(s, seen):
    base = re.sub(r"[^\w\-가-힣]+", "-", s.strip().lower()).strip("-") or "sec"
    n, out = 1, base
    while out in seen: n += 1; out = f"{base}-{n}"
    seen.add(out); return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("md"); ap.add_argument("-o")
    ap.add_argument("--embed", action="store_true"); ap.add_argument("--katex-local")
    a = ap.parse_args()
    src = open(a.md, encoding="utf-8").read()
    base = os.path.dirname(os.path.abspath(a.md))
    md = (MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
          .use(dollarmath_plugin, allow_space=True, double_inline=True).use(footnote_plugin))
    md.add_render_rule("math_inline", lambda self, s, i, o, e: "\\(" + html.escape(s[i].content, quote=False) + "\\)")
    md.add_render_rule("math_block", lambda self, s, i, o, e: "\\[" + html.escape(s[i].content, quote=False) + "\\]")
    md.add_render_rule("math_inline_double", lambda self, s, i, o, e: "\\[" + html.escape(s[i].content, quote=False) + "\\]")
    def fence(self, tokens, idx, opts, env):  # add_render_rule binds rules as methods -> leading self
        t = tokens[idx]
        if t.info.strip() == "mermaid":
            return f'<pre class="mermaid">{html.escape(t.content, quote=False)}</pre>'
        return f'<pre><code class="language-{html.escape(t.info.strip())}">{html.escape(t.content)}</code></pre>'
    md.add_render_rule("fence", fence)
    toks = md.parse(src)
    toc, seen = [], set()
    for i, t in enumerate(toks):
        if t.type == "heading_open" and t.tag in ("h2", "h3"):
            title = toks[i + 1].content; sid = slug(title, seen)
            t.attrSet("id", sid); toc.append((t.tag, sid, title))
    body = md.renderer.render(toks, md.options, {})
    # wrap "![alt](img)" paragraphs followed by italic caption into <figure> is left to the author; just fix paths
    def fix(m):
        p = m.group(1)
        if a.embed and not p.startswith(("http", "data:")):
            f = os.path.join(base, p)
            if os.path.exists(f):
                mt = mimetypes.guess_type(f)[0] or "image/png"
                return f'src="data:{mt};base64,{base64.b64encode(open(f, "rb").read()).decode()}"'
        return m.group(0)
    body = re.sub(r'src="([^"]+)"', fix, body)
    kx = a.katex_local.rstrip("/") if a.katex_local else "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist"
    title = next((t[2] for t in toc), os.path.basename(a.md))
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    if h1: title = re.sub("<[^>]+>", "", h1.group(1))
    nav = "".join(f'<a class="{t}" href="#{s}">{html.escape(x)}</a>' for t, s, x in toc)
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style>
<link rel="stylesheet" href="{kx}/katex.min.css"></head><body><nav>{nav}</nav><main>{body}</main>
<script defer src="{kx}/katex.min.js"></script>
<script defer src="{kx}/contrib/auto-render.min.js" onload="renderMathInElement(document.querySelector('main'),{{delimiters:[{{left:'\\\\[',right:'\\\\]',display:true}},{{left:'\\\\(',right:'\\\\)',display:false}}]}})"></script>
<script type="module">if(document.querySelector('.mermaid')){{const m=await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs');m.default.initialize({{startOnLoad:false}});m.default.run()}}</script>
</body></html>"""
    out = a.o or os.path.splitext(a.md)[0] + ".html"
    open(out, "w", encoding="utf-8").write(doc); print(out)


if __name__ == "__main__":
    main()
