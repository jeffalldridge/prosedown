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

By [Tent Studios, LLC](https://tent.studio).

---

## Quick start

```sh
pip install prosedown

cat > on-simplicity.md <<'EOF'
---
title: "On Simplicity"
author: "Jane Smith"
---

# On Simplicity

The simplest things are often the most profound.

## The Case for Simplicity

When we strip away the unnecessary, what remains is essential.
EOF

prosedown build on-simplicity.md on-simplicity.epub
```

That's a valid EPUB 3.3 — passes [EPUBCheck](https://www.w3.org/publishing/epubcheck/),
opens in Apple Books, Kobo, Calibre, anything that reads ebooks. Two
required frontmatter fields, one Markdown file, no configuration.

When your book outgrows a single file, point `prosedown build` at a
folder of numbered chapters. See `spec/examples/` for four progressively
larger projects.

---

## Why ProseDown

Writing a book in EPUB directly is masochistic — it's a zip file of
XHTML, OPF manifests, NCX navigation documents, and metadata. Existing
tools either:

- **Hide everything** in a closed editor (Vellum, Scrivener) — you can't
  open your manuscript in another app without exporting.
- **Are powerful but heavy** (Pandoc, LaTeX) — full citation engines and
  custom syntax for things 99% of authors don't need.
- **Ship raw EPUB editors** (Sigil, Calibre) — you're hand-editing the
  output format.

ProseDown sits between: **Markdown source files an author can open in
any editor — Obsidian, VS Code, iA Writer, TextEdit — that compile to a
professional EPUB by convention, with no configuration.**

| | Vellum | Scrivener | Pandoc | LaTeX | **ProseDown** |
|---|:-:|:-:|:-:|:-:|:-:|
| Plain text source | ❌ | ❌ | ✅ | ✅ | ✅ |
| Open in any editor | ❌ | ❌ | ✅ | ✅ | ✅ |
| EPUB output | ✅ | ✅ | ✅ | with effort | ✅ |
| Zero configuration | ✅ | ❌ | ❌ | ❌ | ✅ |
| Standard Markdown | n/a | n/a | mostly | ❌ | ✅ |
| Free | $250 once | $59 once | ✅ | ✅ | ✅ |
| macOS / Win / Linux | macOS only | ✅ | ✅ | ✅ | ✅ |
| EPUB → source | ❌ | ❌ | partial | ❌ | ✅ (best-effort) |

ProseDown is **not** for fixed-layout books, picture books, comics,
poetry with line-level control, drama formatting, academic citations,
or media overlays. See the
[scope boundaries](spec/prosedown.md#what-prosedown-is-for-and-not-for)
in the spec.

---

## Two directions, two promises

- **Building** (Markdown → EPUB) is the **primary use case**. Stable,
  reproducible, deterministic. Same source, same output.
- **Deconstructing** (EPUB → Markdown) is **best-effort** with documented
  normalization. The goal is readable Markdown an author would want to
  work with — not a lossless archive of the original EPUB.

Why the asymmetry? Perfect round-trip fidelity would require encoding
every EPUB-specific artifact in the Markdown files, making them
unreadable. ProseDown optimizes for human-readable source files.

---

## What's in this repo

```
prosedown/
  spec/
    prosedown.md             # ← The specification (start here)
    xhtml-mapping.md         # Markdown → XHTML mapping reference
    examples/
      single-file/           # One-file essay
      multi-chapter/         # Numbered chapters in a folder
      multi-part/            # Parts + front/back matter
      with-features/         # Images, captions, glossary

  src/prosedown/             # Reference compiler (Python 3.10+)
    __init__.py
    data/prosedown-default.css

  tests/
    test_suite.py            # 36 synthetic tests, all green

  pyproject.toml             # Installable as `pip install prosedown`
```

---

## CLI

```sh
# Markdown → EPUB
prosedown build path/to/project path/to/output.epub

# EPUB → Markdown (best-effort)
prosedown deconstruct path/to/book.epub path/to/output-project/
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
python tests/test_suite.py   # 36 synthetic tests
```

Requires **Python 3.10+**.

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
mapping reference.

---

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
