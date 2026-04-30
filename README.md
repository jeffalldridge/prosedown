# ProseDown

> **Write books in Markdown. Compile to EPUB.**
> Like [Fountain](https://fountain.io/) is for screenplays, ProseDown is
> for ebooks: plain text that compiles to a complex format. Two lines of
> frontmatter, one Markdown file, valid EPUB 3.3.

[![CI](https://github.com/jeffalldridge/prosedown/actions/workflows/ci.yml/badge.svg)](https://github.com/jeffalldridge/prosedown/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/prosedown)](https://pypi.org/project/prosedown/)
[![Python](https://img.shields.io/pypi/pyversions/prosedown)](https://pypi.org/project/prosedown/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![EPUB 3.3](https://img.shields.io/badge/EPUB-3.3-green)](https://www.w3.org/TR/epub-33/)

**🌐 [jeffalldridge.github.io/prosedown](https://jeffalldridge.github.io/prosedown/)** — live site, full spec, cheat sheet.

By [Tent Studios, LLC](https://tent.studio).

---

## Why this exists

Most ebook tools fall into one of three buckets — and each forces a
tradeoff most authors don't want to make:

- **Closed editors** (Vellum, Scrivener) hide everything in a closed
  app. You can't open your manuscript anywhere else without exporting.
- **Power tools** (Pandoc, LaTeX) are heavy. Full citation engines and
  custom syntax for things 99% of authors don't need.
- **Raw editors** (Sigil, Calibre) make you hand-edit XHTML inside a
  zip file. Useful for fixing existing books, painful for writing
  new ones.

|  | Vellum | Scrivener | Pandoc | LaTeX | **ProseDown** |
|---|:-:|:-:|:-:|:-:|:-:|
| Plain text source | ❌ | ❌ | ✅ | ✅ | ✅ |
| Open in any editor | ❌ | ❌ | ✅ | ✅ | ✅ |
| EPUB output | ✅ | ✅ | ✅ | with effort | ✅ |
| Zero configuration | ✅ | ❌ | ❌ | ❌ | ✅ |
| Standard Markdown | n/a | n/a | mostly | ❌ | ✅ |
| Free | $250 once | $59 once | ✅ | ✅ | ✅ |
| macOS / Win / Linux | macOS only | ✅ | ✅ | ✅ | ✅ |
| EPUB → source | ❌ | ❌ | partial | ❌ | ✅ (best-effort) |

ProseDown sits between: **plain Markdown source files an author can open
in any editor — Obsidian, VS Code, iA Writer, TextEdit — that compile to
a professional EPUB by convention, with no configuration.**

ProseDown is **not** for fixed-layout books, picture books, comics,
poetry with line-level control, drama formatting, academic citations,
or media overlays. See the
[scope boundaries](spec/prosedown.md#what-prosedown-is-for-and-not-for)
in the spec.

---

## Five design principles

The decisions that shape every part of the format.

1. **One file is enough.** A single `.md` with two YAML lines is a
   valid project. The barrier to entry is zero.
2. **Convention over configuration.** Cover auto-detected. CSS
   auto-detected. Chapter order from filenames. Authors shouldn't
   configure what can be inferred.
3. **Standard everything.** [CommonMark](https://commonmark.org/)
   Markdown. Standard YAML. No custom syntax. Lock-in is the enemy of
   adoption — and your files should outlive any single tool.
4. **Two directions.** Build is primary, deterministic, EPUBCheck-clean.
   Deconstruct is best-effort and practical, not a lossless archive.
5. **Non-destructive.** Opens cleanly in Obsidian, Hugo, Jekyll, or
   any other Markdown tool. A format that fights your other tools
   isn't a format worth adopting.

---

## The whole tool, in seven lines

No configuration files, no project initializer, no template wizard.

```sh
cat > on-simplicity.md <<'EOF'
---
title: "On Simplicity"
author: "Jane Smith"
---

# On Simplicity

The simplest things are often the most profound.
EOF

prosedown build on-simplicity.md on-simplicity.epub
```

That's a valid [EPUB 3.3](https://www.w3.org/TR/epub-33/) — passes
[EPUBCheck](https://www.w3.org/publishing/epubcheck/), opens in Apple
Books, Kobo, Calibre, anything that reads ebooks. Two required
frontmatter fields, one Markdown file, no configuration.

When your book outgrows a single file, point `prosedown build` at a
folder of numbered chapters. See [`spec/examples/`](spec/examples/) for
four progressively larger projects.

---

## How `build` works

Markdown source on the left, EPUB 3.3 on the right, a small handful of
well-defined steps in the middle.

```
       your project           prosedown build              EPUB 3.3
   ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
   │ book.md          │     │ parse YAML       │     │ META-INF/        │
   │ 01-intro.md      │ ──▶ │ resolve files    │ ──▶ │   container.xml  │
   │ 02-chapter.md    │     │ render Markdown  │     │ OEBPS/           │
   │ cover.jpg        │     │ build OPF/NCX    │     │   chapters/      │
   │ style.css        │     │ pack ZIP         │     │   images/        │
   │                  │     │                  │     │   nav.xhtml      │
   │                  │     │                  │     │   content.opf    │
   │                  │     │                  │     │ mimetype         │
   └──────────────────┘     └──────────────────┘     └──────────────────┘
                            deterministic · EPUBCheck-clean
                            same source → same bytes
```

Everything is auto-detected: cover by filename, CSS by filename,
chapter order by numeric prefix. Same source produces the same bytes —
diff-clean under git, reproducible builds work.

---

## How `deconstruct` works (the other direction)

An existing EPUB on the left, a clean Markdown project you'd actually
want to edit on the right.

```
      existing.epub             deconstruct            Markdown project
   ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
   │ .epub (zip)      │     │ read OPF         │     │ book.md          │
   │   XHTML          │ ──▶ │ classify roles   │ ──▶ │ 000-cover.md     │
   │   + assets       │     │ walk spine       │     │ 001-chapter.md   │
   │   + OPF          │     │ XHTML → Markdown │     │ 002-chapter.md   │
   │                  │     │ extract images   │     │ ...              │
   │                  │     │ extract css      │     │ images/          │
   │                  │     │                  │     │ css/             │
   │                  │     │                  │     │                  │
   └──────────────────┘     └──────────────────┘     └──────────────────┘
                            best-effort · documented normalization
```

Building is the **primary** use case — stable and deterministic.
Deconstruction is **best-effort** with documented normalization. The
goal is readable Markdown an author would want to edit, not a lossless
archive of the original EPUB.

---

## ProseDown at a glance

If you only read one section, read this one. The full
[spec](spec/prosedown.md) is the source of truth; this is the cheat sheet.

### Required frontmatter

Two fields. That's the floor. Everything else is inferred or optional.

```yaml
---
title: "Your Book"
author: "You"
---
```

### Optional frontmatter

```yaml
language: en           # default: en
publisher: "…"
date: 2026-04-30
isbn: "978-…"
description: |
  Short blurb.
cover: "cover.jpg"
css: "style.css"
```

ProseDown synthesizes a deterministic UUID from `title + author + language`.

### Project layouts

```
# Single-file project — one file, one essay, one EPUB.
my-essay.md     # frontmatter + body

# Multi-chapter project — filename order = chapter order.
my-book/
  book.md          # frontmatter only
  00-copyright.md
  01-chapter-1.md
  02-chapter-2.md
  cover.jpg        # auto-detected
  style.css        # auto-detected
```

### Conventional slugs (auto-classified by role)

- **Frontmatter**: `copyright`, `dedication`, `acknowledgments`, `foreword`, `preface`
- **Part dividers**: `part-1`, `part-2`, …
- **Backmatter**: `afterword`, `about-the-author`, `colophon`, `notes`
- **Anything else**: chapter

### Title resolution

1. Frontmatter `title:` (if set)
2. First `#` heading in body
3. Deslugified filename

Same logic on deconstruct — round-trips preserve the title source.

### Standard Markdown

[CommonMark](https://commonmark.org/) plus GitHub-flavored extensions:
tables, definition lists, fenced code, footnotes (`[^1]`). No custom
dialect.

### Excluded files

Filenames starting with `_` are skipped at build time. Useful for
parking drafts in the same folder.

```
_09-deleted-scene.md
_draft.md
```

---

## Pick your path

Three ways into ProseDown depending on what you're trying to do.

### 1. I want to *write* a book

You're an author. You want to focus on the words and have something
publishable come out the other end.

- [Five-minute quickstart](docs/quickstart.md)
- [Single-file example](spec/examples/single-file/) — start here
- [Multi-chapter example](spec/examples/multi-chapter/) — when one file isn't enough
- [Multi-part example](spec/examples/multi-part/) — front/back matter, parts
- [Features example](spec/examples/with-features/) — images, captions, glossary

### 2. I want to *understand* the format

You're evaluating ProseDown for a workflow, a tool you're building, or
out of curiosity about how the design hangs together.

- [The spec](spec/prosedown.md) — single source of truth
- [Why ProseDown](docs/why-prosedown.md) — design rationale
- [XHTML mapping reference](spec/xhtml-mapping.md) — for implementers
- [Roadmap](ROADMAP.md) — where it's going

### 3. I want to *build* on it

You're writing a tool, plugin, or alternate compiler. The spec is open
and the reference compiler is MIT.

- [PyPI package](https://pypi.org/project/prosedown/) — `pip install prosedown`
- [Contributing](CONTRIBUTING.md) — setup, PR checklist, what fits
- [Help wanted](ROADMAP.md#help-wanted) — especially a Rust or Go compiler for v1.0
- [Live site](https://jeffalldridge.github.io/prosedown/) — landing page + spec

---

## Install

```sh
pip install prosedown
```

Requires **Python 3.10+**.

```sh
prosedown --help
prosedown --version
prosedown build  path/to/project   path/to/output.epub
prosedown deconstruct  path/to/book.epub  path/to/output-project/
```

The `build` path uses only MIT- and BSD-licensed dependencies. The
`deconstruct` path additionally pulls in `html2text` (GPL-3.0+) and
`EbookLib` (AGPL-3.0+) — see [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

---

## Develop

```sh
git clone https://github.com/jeffalldridge/prosedown
cd prosedown
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

prosedown --help
python tests/test_suite.py   # 36 synthetic tests, all green
```

### Running against a real-world corpus

The synthetic tests in `tests/test_suite.py` always run. To additionally
exercise ProseDown against real EPUBs from Standard Ebooks, Project
Gutenberg, etc., point at a local corpus:

```sh
PROSEDOWN_CORPUS=/path/to/corpus python tests/test_suite.py
```

The corpus is **not redistributed via this repo** — it can include
copyrighted material. The expected layout is documented in the test file.

---

## What's in this repo

```
prosedown/
  spec/
    prosedown.md              # ← The specification (start here)
    xhtml-mapping.md          # Markdown → XHTML mapping reference
    examples/
      single-file/            # One-file essay
      multi-chapter/          # Numbered chapters in a folder
      multi-part/             # Parts + front/back matter
      with-features/          # Images, captions, glossary

  src/prosedown/              # Reference compiler (Python 3.10+)
    __init__.py
    data/prosedown-default.css

  tests/
    test_suite.py             # 36 synthetic tests, all green

  docs/
    site/                     # GitHub Pages site source
    quickstart.md
    why-prosedown.md

  scripts/
    build_site.py             # Renders spec/prosedown.md → site

  pyproject.toml              # Installable as `pip install prosedown`
```

---

## Spec

The current spec is at [`spec/prosedown.md`](spec/prosedown.md), version
**0.6.1**. Pre-1.0; minor refinements likely before 1.0. The spec uses
**MUST**, **SHOULD**, and **MAY** per
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) where two compilers
need to agree on exact behavior.

A conforming compiler **MUST** produce EPUB 3.3 output that passes
[EPUBCheck](https://www.w3.org/publishing/epubcheck/) without errors.

Implementations in other languages are welcome — see
[`spec/xhtml-mapping.md`](spec/xhtml-mapping.md) for the Markdown → XHTML
mapping reference. The full spec also lives as a rendered HTML page at
[jeffalldridge.github.io/prosedown/spec/](https://jeffalldridge.github.io/prosedown/spec/).

---

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for what's planned for v0.7, v1.0, and
beyond — plus what's deliberately out of scope.

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the setup, PR
checklist, and the difference between spec changes and code changes.

For security issues, see [`SECURITY.md`](SECURITY.md).

---

## Credits

- Built on [CommonMark](https://commonmark.org/) (Markdown), [EPUB 3.3](https://www.w3.org/TR/epub-33/),
  and [XHTML 1.1](https://www.w3.org/TR/xhtml11/).
- Reference implementation in Python: [`Markdown`](https://github.com/Python-Markdown/markdown),
  [`PyYAML`](https://github.com/yaml/pyyaml), [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/),
  [`lxml`](https://lxml.de/), [`html2text`](https://github.com/Alir3z4/html2text),
  [`EbookLib`](https://github.com/aerkalov/ebooklib).
- Conceptual ancestor: [Fountain](https://fountain.io/) (plain text for
  screenplays).

Full attribution in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

---

## License

MIT. © 2026 Jeff Alldridge / Tent Studios, LLC.
