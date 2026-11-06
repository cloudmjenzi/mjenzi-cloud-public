#!/usr/bin/env python3
"""Build the Mjenzi Cloud blog from Markdown. Standard library only.

    python3 blog/build.py

Reads   blog/posts/*.md   (front matter + Markdown)
Writes  blog/<slug>.html, blog/index.html, blog/feed.xml, sitemap.xml,
        and the "Latest from the blog" strip in index.html.

Front matter (between --- lines at the top of each post):
    title:   Post title                       (required)
    date:    2026-11-06                        (required, YYYY-MM-DD)
    summary: One or two sentences for cards    (required)
    author:  Mjenzi Cloud team                 (optional)
    tags:    Cloud, Africa                     (optional, comma separated)
    image:   /blog/images/cover.jpg            (optional cover image)
    draft:   true                              (optional, skips the post)
"""
from __future__ import annotations

import html
import re
import sys
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
POSTS = BLOG / "posts"
SITE = "https://mjenzi.cloud"
ASSET_V = "20261106b"  # bump when assets/styles.css or assets/common.js change
STATIC_PAGES = [("/", "1.0"), ("/platform.html", "0.9"), ("/assessment.html", "0.8"),
                ("/sizing.html", "0.8"), ("/cloud-config.html", "0.8"), ("/blog/", "0.7"),
                ("/privacy.html", "0.3")]

esc = html.escape


# ---------------------------------------------------------------- Markdown
def inline(text: str) -> str:
    """Inline Markdown: code, images, links, bold, italic. Input is raw text."""
    codes: list[str] = []

    def keep_code(m):
        codes.append(f"<code>{esc(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = esc(text, quote=False)

    def safe_url(u: str) -> str:
        u = html.unescape(u).strip()
        return esc(u) if re.match(r"^(https?:|mailto:|tel:|/|#|\.{0,2}/?[\w-])", u) and not u.lower().startswith("javascript:") else "#"

    def stash(h: str) -> str:  # protect finished HTML from the bold/italic passes
        codes.append(h)
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
                  lambda m: stash(f'<img src="{safe_url(m.group(2))}" alt="{m.group(1)}" loading="lazy">'), text)

    def link(m):
        url = safe_url(m.group(2))
        ext = url.startswith("http") and not url.startswith(SITE)
        attrs = ' target="_blank" rel="noopener"' if ext else ""
        return stash(f'<a href="{url}"{attrs}>') + m.group(1) + stash("</a>")

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def markdown(src: str) -> tuple[str, list[tuple[str, str]]]:
    """Block Markdown -> (html, [(id, h2 text)]) for headings, lists, quotes, code, tables, hr."""
    lines = src.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        # fenced code
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{esc(chr(10).join(buf))}</code></pre>")
            continue
        # heading
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            hid = slugify(re.sub(r"[`*_\[\]()]", "", text))
            if level == 2:
                toc.append((hid, re.sub(r"<[^>]+>", "", inline(text))))
            out.append(f'<h{level} id="{hid}">{inline(text)}</h{level}>')
            i += 1
            continue
        # horizontal rule
        if re.match(r"^(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        # blockquote
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            inner, _ = markdown("\n".join(buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue
        # table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            t = ["<div class=\"table-wrap\"><table><thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue
        # lists
        m = re.match(r"^(\s*)([-*]|\d+[.)])\s+", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < len(lines):
                mm = re.match(r"^\s*([-*]|\d+[.)])\s+(.*)$", lines[i])
                if mm and (mm.group(1)[0].isdigit()) == ordered:
                    items.append(mm.group(2))
                elif lines[i].startswith(("  ", "\t")) and items and lines[i].strip():
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
            continue
        # paragraph
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,4}\s|```|>|(\s*)([-*]|\d+[.)])\s|(-{3,}|\*{3,})\s*$)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if not buf:  # safety: unknown construct, treat as text
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")
    return "\n".join(out), toc


# ---------------------------------------------------------------- Posts
def load_posts() -> list[dict]:
    posts = []
    for path in sorted(POSTS.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
        if not m:
            sys.exit(f"{path.name}: missing front matter (--- ... --- at the top)")
        meta = {}
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"')
        if meta.get("draft", "").lower() in ("true", "yes", "1"):
            continue
        for k in ("title", "date", "summary"):
            if not meta.get(k):
                sys.exit(f"{path.name}: front matter needs '{k}:'")
        try:
            d = date.fromisoformat(meta["date"])
        except ValueError:
            sys.exit(f"{path.name}: date must be YYYY-MM-DD")
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)
        body, toc = markdown(m.group(2))
        words = len(re.sub(r"<[^>]+>", " ", body).split())
        posts.append({
            "slug": slugify(slug), "title": meta["title"], "date": d, "summary": meta["summary"],
            "author": meta.get("author") or "Mjenzi Cloud team",
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
            "image": meta.get("image", ""), "body": body, "toc": toc,
            "minutes": max(1, -(-words // 200)),
        })
    posts.sort(key=lambda p: (p["date"], p["title"]), reverse=True)
    return posts


def nice_date(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def head(title: str, desc: str, canonical: str, og_type="website", image="", extra="") -> str:
    img = f'\n  <meta property="og:image" content="{esc(SITE + image if image.startswith("/") else image)}">' if image else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="canonical" href="{SITE}{canonical}">
  <link rel="alternate" type="application/rss+xml" title="Mjenzi Cloud blog" href="/blog/feed.xml">
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{SITE}{canonical}">{img}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/styles.css?v={ASSET_V}">{extra}
</head>"""


FOOT = f"""<script src="/assets/common.js?v={ASSET_V}"></script>
</body>
</html>
"""


def tag_chips(tags: list[str], link=True) -> str:
    if link:
        return "".join(f'<a class="tchip" href="/blog/?tag={esc(slugify(t))}">{esc(t)}</a>' for t in tags)
    return "".join(f'<span class="tchip">{esc(t)}</span>' for t in tags)


def card(p: dict) -> str:
    tags = " ".join(slugify(t) for t in p["tags"])
    cover = (f'<img class="post-cover" src="{esc(p["image"])}" alt="" loading="lazy">' if p["image"]
             else f'<div class="post-cover gen" aria-hidden="true"><span>{esc(p["tags"][0] if p["tags"] else "Mjenzi Cloud")}</span></div>')
    return f"""      <a class="card post-card reveal" href="/blog/{p['slug']}.html" data-tags="{esc(tags)}">
        {cover}
        <div class="post-meta"><time datetime="{p['date']}">{nice_date(p['date'])}</time> · {p['minutes']} min read</div>
        <h3>{esc(p['title'])}</h3>
        <p>{esc(p['summary'])}</p>
        <div class="tchips">{tag_chips(p['tags'], link=False)}</div>
      </a>"""


def write(path: Path, text: str) -> None:
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        print("  wrote", path.relative_to(ROOT))


def build_post(p: dict, posts: list[dict]) -> str:
    idx = posts.index(p)
    newer = posts[idx - 1] if idx > 0 else None
    older = posts[idx + 1] if idx + 1 < len(posts) else None
    related = [q for q in posts if q is not p and set(q["tags"]) & set(p["tags"])][:2] or [q for q in posts if q is not p][:2]
    toc = ""
    if len(p["toc"]) >= 3:
        toc = '<nav class="toc" aria-label="On this page"><b>On this page</b>' + "".join(
            f'<a href="#{hid}">{esc(t)}</a>' for hid, t in p["toc"]) + "</nav>"
    ld = {
        "@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
        "description": p["summary"], "datePublished": p["date"].isoformat(),
        "author": {"@type": "Organization", "name": p["author"]},
        "publisher": {"@type": "Organization", "name": "Mjenzi Cloud", "url": SITE},
        "mainEntityOfPage": f"{SITE}/blog/{p['slug']}.html",
    }
    import json
    nav = ""
    if newer or older:
        nav = '<div class="post-nav">' + (
            f'<a href="/blog/{older["slug"]}.html"><small>← Older</small>{esc(older["title"])}</a>' if older else "<span></span>") + (
            f'<a class="next" href="/blog/{newer["slug"]}.html"><small>Newer →</small>{esc(newer["title"])}</a>' if newer else "") + "</div>"
    rel = ""
    if related:
        rel = f"""
<section class="alt" style="padding:64px 0">
  <div class="wrap">
    <div class="eyebrow">Keep reading</div>
    <div class="grid g2 post-grid" style="margin-top:12px">
{chr(10).join(card(q) for q in related)}
    </div>
  </div>
</section>"""
    share_url = esc(f"{SITE}/blog/{p['slug']}.html")
    share_text = esc(p["title"])
    return head(f"{p['title']} — Mjenzi Cloud blog", p["summary"], f"/blog/{p['slug']}.html", "article", p["image"],
                f'\n  <script type="application/ld+json">{json.dumps(ld)}</script>') + f"""
<body data-page="blog">
<article class="post">
  <header class="post-head wrap">
    <a class="back" href="/blog/">← All posts</a>
    <div class="tchips">{tag_chips(p['tags'])}</div>
    <h1>{esc(p['title'])}</h1>
    <p class="post-lede">{esc(p['summary'])}</p>
    <div class="post-meta">{esc(p['author'])} · <time datetime="{p['date']}">{nice_date(p['date'])}</time> · {p['minutes']} min read</div>
  </header>
  <div class="wrap post-layout">
    <div class="prose">
{p['body']}
      <div class="post-cta">
        <b>Talk to a Mjenzi engineer</b>
        <span>Questions about this post or your own cloud and AI plans? We reply within one business day.</span>
        <div class="actions"><a class="btn btn-primary btn-sm" href="/#contact">Contact us</a><a class="btn btn-ghost btn-sm" href="https://wa.me/61405342017" target="_blank" rel="noopener">WhatsApp</a></div>
      </div>
      <div class="share">Share:
        <a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener">LinkedIn</a>
        <a href="https://x.com/intent/post?url={share_url}&amp;text={share_text}" target="_blank" rel="noopener">X</a>
        <a href="https://wa.me/?text={share_text}%20{share_url}" target="_blank" rel="noopener">WhatsApp</a>
        <a href="mailto:?subject={share_text}&amp;body={share_url}">Email</a>
      </div>
      {nav}
    </div>
    {toc}
  </div>
</article>{rel}
{FOOT}"""


def build_index(posts: list[dict]) -> str:
    all_tags = sorted({t for p in posts for t in p["tags"]}, key=str.lower)
    filters = '<button class="tchip active" data-tag="">All</button>' + "".join(
        f'<button class="tchip" data-tag="{esc(slugify(t))}">{esc(t)}</button>' for t in all_tags)
    cards = "\n".join(card(p) for p in posts) or '      <p>No posts yet.</p>'
    return head("Blog — Mjenzi Cloud", "News, guides and engineering notes on cloud, GPU and AI infrastructure in Africa and Australia.", "/blog/") + f"""
<body data-page="blog">
<section class="tool-hero">
  <div class="wrap">
    <div class="eyebrow">Blog</div>
    <h1 style="font-size:clamp(2.2rem,5vw,3.4rem)">Notes from the cloud builders.</h1>
    <p style="max-width:680px">News, practical guides and engineering notes on sovereign cloud, GPU infrastructure and AI in Africa and Australia.</p>
    <div class="tchips filters" role="group" aria-label="Filter by topic">{filters}</div>
  </div>
</section>
<section style="padding-top:12px">
  <div class="wrap">
    <div class="grid g3 post-grid" id="posts">
{cards}
    </div>
    <p class="empty" id="empty" hidden>No posts with that tag yet.</p>
    <p style="margin-top:40px;color:var(--muted)">Follow along with the <a href="/blog/feed.xml" style="color:var(--accent)">RSS feed</a>.</p>
  </div>
</section>
<script>
  (function () {{
    const btns = document.querySelectorAll(".filters .tchip"), cards = document.querySelectorAll("#posts .post-card");
    function apply(tag) {{
      let shown = 0;
      cards.forEach((c) => {{ const ok = !tag || c.dataset.tags.split(" ").includes(tag); c.hidden = !ok; if (ok) {{ shown++; c.classList.add("in"); }} }});
      btns.forEach((b) => b.classList.toggle("active", b.dataset.tag === tag));
      document.getElementById("empty").hidden = shown > 0;
    }}
    btns.forEach((b) => b.addEventListener("click", () => {{
      const tag = b.dataset.tag; apply(tag);
      history.replaceState(null, "", tag ? "?tag=" + tag : location.pathname);
    }}));
    apply(new URLSearchParams(location.search).get("tag") || "");
  }})();
</script>
{FOOT}"""


def build_feed(posts: list[dict]) -> str:
    items = []
    for p in posts[:20]:
        dt = datetime(p["date"].year, p["date"].month, p["date"].day, 9, tzinfo=timezone.utc)
        url = f"{SITE}/blog/{p['slug']}.html"
        items.append(f"""  <item>
    <title>{esc(p['title'])}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{format_datetime(dt)}</pubDate>
    <description>{esc(p['summary'])}</description>
{''.join(f'    <category>{esc(t)}</category>{chr(10)}' for t in p['tags'])}  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>Mjenzi Cloud blog</title>
  <link>{SITE}/blog/</link>
  <atom:link href="{SITE}/blog/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Cloud, GPU and AI infrastructure in Africa and Australia.</description>
  <language>en</language>
{chr(10).join(items)}
</channel>
</rss>
"""


def build_sitemap(posts: list[dict]) -> str:
    urls = [f"  <url><loc>{SITE}{u}</loc><priority>{pr}</priority></url>" for u, pr in STATIC_PAGES]
    urls += [f"  <url><loc>{SITE}/blog/{p['slug']}.html</loc><lastmod>{p['date']}</lastmod><priority>0.6</priority></url>" for p in posts]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"


def update_home(posts: list[dict]) -> None:
    home = ROOT / "index.html"
    s = home.read_text(encoding="utf-8")
    start, end = "<!-- blog:latest -->", "<!-- /blog:latest -->"
    if start not in s:
        return
    block = f"""{start}
<section id="blog" class="alt">
  <div class="wrap">
    <div class="section-head reveal">
      <div class="eyebrow">From the blog</div>
      <h2>Latest notes from the cloud builders.</h2>
    </div>
    <div class="grid g3 post-grid">
{chr(10).join(card(p) for p in posts[:3])}
    </div>
    <div class="actions" style="margin-top:28px"><a class="btn btn-ghost" href="/blog/">All posts →</a></div>
  </div>
</section>
{end}""" if posts else f"{start}\n{end}"
    new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, s, flags=re.S)
    write(home, new)


def main() -> None:
    posts = load_posts()
    slugs = [p["slug"] for p in posts]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        sys.exit(f"Two posts share the same name: {', '.join(dupes)}")
    keep = {f"{p['slug']}.html" for p in posts} | {"index.html"}
    for old in BLOG.glob("*.html"):  # remove pages for deleted/renamed/drafted posts
        if old.name not in keep:
            old.unlink()
            print("  removed", old.relative_to(ROOT))
    for p in posts:
        write(BLOG / f"{p['slug']}.html", build_post(p, posts))
    write(BLOG / "index.html", build_index(posts))
    write(BLOG / "feed.xml", build_feed(posts))
    write(ROOT / "sitemap.xml", build_sitemap(posts))
    update_home(posts)
    print(f"Blog built: {len(posts)} post(s).")


if __name__ == "__main__":
    main()
