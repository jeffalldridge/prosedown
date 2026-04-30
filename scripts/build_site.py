#!/usr/bin/env python3
"""Render auxiliary pages for the GitHub Pages site.

Reads:
    spec/prosedown.md           → docs/site/spec/index.html
    (also produces sitemap.xml + robots.txt for the deploy)

Usage:
    python Scripts/build_site.py [<output-dir>]

The output directory defaults to docs/site/. The CI workflow stages
docs/site/ into _site/ before deploy, so we write directly into the
source tree at docs/site/spec/, plus generate sitemap.xml and
robots.txt next to index.html.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import textwrap
from pathlib import Path

import markdown


SITE_URL = "https://jeffalldridge.github.io/prosedown/"
SITE_NAME = "ProseDown"

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_MD = REPO_ROOT / "spec" / "prosedown.md"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "site"


SPEC_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The ProseDown Specification {version}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="The full ProseDown specification — a CommonMark + YAML format for writing books in Markdown that compile to EPUB 3.3. RFC 2119 normative language where two compilers need to agree.">
<meta name="theme-color" content="#0d0d12">
<meta name="color-scheme" content="dark light">
<meta name="author" content="Jeff Alldridge / Tent Studios, LLC">

<meta property="og:title" content="The ProseDown Specification">
<meta property="og:description" content="The full specification for ProseDown — Markdown to EPUB 3.3 with two required frontmatter fields and no custom syntax.">
<meta property="og:type" content="article">
<meta property="og:url" content="{site_url}spec/">
<meta property="og:image" content="{site_url}og-image.png">
<meta property="og:image:width" content="1280">
<meta property="og:image:height" content="640">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="The ProseDown Specification">
<meta name="twitter:description" content="The full specification for ProseDown — Markdown to EPUB 3.3.">
<meta name="twitter:image" content="{site_url}og-image.png">

<link rel="canonical" href="{site_url}spec/">
<link rel="icon" type="image/png" href="../favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="../favicon-192.png" sizes="192x192">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<link rel="manifest" href="../manifest.webmanifest">

<link rel="stylesheet" href="../style.css">
<link rel="stylesheet" href="../spec.css">

<script type="application/ld+json">
{{
    "@context": "https://schema.org",
    "@graph": [
        {{
            "@type": "TechArticle",
            "@id": "{site_url}spec/#article",
            "headline": "The ProseDown Specification",
            "name": "ProseDown Specification {version}",
            "description": "The full ProseDown specification — a CommonMark + YAML format for writing books in Markdown that compile to EPUB 3.3.",
            "url": "{site_url}spec/",
            "image": "{site_url}og-image.png",
            "datePublished": "{date}",
            "dateModified": "{date}",
            "inLanguage": "en",
            "wordCount": {word_count},
            "license": "https://opensource.org/licenses/MIT",
            "isAccessibleForFree": true,
            "author": {{
                "@type": "Person",
                "name": "Jeff Alldridge",
                "url": "https://tentstudios.com"
            }},
            "publisher": {{
                "@type": "Organization",
                "name": "Tent Studios, LLC",
                "url": "https://tentstudios.com"
            }},
            "isPartOf": {{
                "@id": "{site_url}#website"
            }}
        }},
        {{
            "@type": "BreadcrumbList",
            "itemListElement": [
                {{
                    "@type": "ListItem",
                    "position": 1,
                    "name": "ProseDown",
                    "item": "{site_url}"
                }},
                {{
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Specification",
                    "item": "{site_url}spec/"
                }}
            ]
        }}
    ]
}}
</script>
</head>
<body>

<a class="skip-link" href="#main">Skip to main content</a>

<nav class="topnav" aria-label="Primary">
    <div class="container">
        <a class="topnav-brand" href="../">
            <span class="prose">prose</span><span class="down">down</span>
        </a>
        <ul class="topnav-links">
            <li><a href="../#why">Why</a></li>
            <li><a href="../#cheat-sheet">Cheat sheet</a></li>
            <li><a href="./" aria-current="page">Spec</a></li>
            <li><a href="../#install">Install</a></li>
            <li><a href="https://github.com/jeffalldridge/prosedown">GitHub</a></li>
        </ul>
    </div>
</nav>

<main id="main">

<header class="spec-hero">
    <div class="container">
        <p class="breadcrumb"><a href="../">ProseDown</a> <span aria-hidden="true">/</span> <span>Specification</span></p>
        <h1>The ProseDown Specification</h1>
        <p class="lede">{version} — the source of truth for any conforming compiler. The site you're on is the friendly intro; this is the contract.</p>
        <p class="spec-meta">
            <a href="https://github.com/jeffalldridge/prosedown/blob/main/spec/prosedown.md">View on GitHub</a> ·
            <a href="https://github.com/jeffalldridge/prosedown/blob/main/spec/xhtml-mapping.md">XHTML mapping</a> ·
            <a href="../#cheat-sheet">Cheat sheet</a>
        </p>
    </div>
</header>

<article class="spec container" id="spec-body">
{body}
</article>

</main>

<footer class="footer">
    <div class="container">
        <p>By <a href="https://tentstudios.com">Tent Studios, LLC</a>. MIT licensed. <a href="https://github.com/jeffalldridge/prosedown">Source on GitHub</a> · <a href="../">Home</a> · <a href="https://github.com/jeffalldridge/prosedown/blob/main/ROADMAP.md">Roadmap</a></p>
    </div>
</footer>

</body>
</html>
"""


def slugify(text: str) -> str:
    """Generate a stable, URL-safe slug for a heading."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "section"


def render_spec(md_path: Path) -> tuple[str, str, str, int]:
    """Render the spec Markdown to HTML. Returns (title, version, body_html, word_count)."""
    raw = md_path.read_text(encoding="utf-8")

    # Pull a title and version from the first lines of the document.
    title = "ProseDown"
    version = ""
    for line in raw.splitlines()[:10]:
        if line.startswith("# "):
            title = line[2:].strip()
        m = re.match(r"\*\*Version\s+([^*]+?)\*\*", line.strip())
        if m:
            version = m.group(1).strip()

    md = markdown.Markdown(
        extensions=[
            "extra",            # tables, fenced code, def_list, footnotes…
            "toc",              # heading anchors + TOC
            "sane_lists",
            "smarty",           # smart quotes
            "admonition",
        ],
        extension_configs={
            "toc": {"permalink": "#", "toc_depth": "2-4"},
        },
        output_format="html5",
    )
    body_html = md.convert(raw)
    word_count = len(re.findall(r"\b\w+\b", raw))
    return title, version, body_html, word_count


def write_sitemap(out_dir: Path) -> None:
    """Emit a sitemap.xml covering the home page and the spec page."""
    today = dt.date.today().isoformat()
    sitemap = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>{SITE_URL}</loc>
                <lastmod>{today}</lastmod>
                <changefreq>weekly</changefreq>
                <priority>1.0</priority>
            </url>
            <url>
                <loc>{SITE_URL}spec/</loc>
                <lastmod>{today}</lastmod>
                <changefreq>monthly</changefreq>
                <priority>0.9</priority>
            </url>
        </urlset>
        """)
    (out_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_robots(out_dir: Path) -> None:
    """Emit a permissive robots.txt that points crawlers at the sitemap."""
    robots = textwrap.dedent(f"""\
        User-agent: *
        Allow: /

        Sitemap: {SITE_URL}sitemap.xml
        """)
    (out_dir / "robots.txt").write_text(robots, encoding="utf-8")


def write_manifest(out_dir: Path) -> None:
    """Emit a minimal web app manifest pointing at the favicon set."""
    manifest = textwrap.dedent("""\
        {
            "name": "ProseDown",
            "short_name": "ProseDown",
            "description": "Write books in Markdown, compile to EPUB.",
            "start_url": "/prosedown/",
            "scope": "/prosedown/",
            "display": "standalone",
            "background_color": "#0d0d12",
            "theme_color": "#0d0d12",
            "icons": [
                { "src": "favicon-192.png", "sizes": "192x192", "type": "image/png" },
                { "src": "favicon-512.png", "sizes": "512x512", "type": "image/png" }
            ]
        }
        """)
    (out_dir / "manifest.webmanifest").write_text(manifest, encoding="utf-8")


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    spec_dir = out_dir / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)

    title, version, body_html, word_count = render_spec(SPEC_MD)
    today_iso = dt.date.today().isoformat()

    rendered = SPEC_PAGE_TEMPLATE.format(
        title=title,
        version=version or "v0.6.1",
        site_url=SITE_URL,
        site_name=SITE_NAME,
        date=today_iso,
        word_count=word_count,
        body=body_html,
    )

    (spec_dir / "index.html").write_text(rendered, encoding="utf-8")
    write_sitemap(out_dir)
    write_robots(out_dir)
    write_manifest(out_dir)

    print(f"Wrote {spec_dir / 'index.html'}")
    print(f"Wrote {out_dir / 'sitemap.xml'}")
    print(f"Wrote {out_dir / 'robots.txt'}")
    print(f"Wrote {out_dir / 'manifest.webmanifest'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
