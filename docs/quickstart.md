# Quickstart

Five minutes to your first EPUB.

## Install

```sh
pip install prosedown
```

Requires Python 3.10+.

Verify:

```sh
prosedown --help
```

## Single-file project

```sh
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

Open `on-simplicity.epub` in Apple Books, Kobo, Calibre, or any e-reader.

## Multi-chapter project

When the book outgrows a single file, switch to a folder. Order is by
filename:

```
my-book/
  book.md           # frontmatter + title page
  01-intro.md
  02-chapter-one.md
  03-chapter-two.md
  cover.jpg         # auto-detected
```

```sh
prosedown build my-book/ my-book.epub
```

`book.md` holds the frontmatter (`title`, `author`, optional fields).
Cover image is auto-detected by filename. Chapters compile in order.

See [`spec/examples/multi-chapter/`](../spec/examples/multi-chapter/) for
a working example.

## Deconstruct an EPUB

Going the other direction:

```sh
prosedown deconstruct existing-book.epub recovered-project/
```

This produces a folder of Markdown chapters. Output is **best-effort** —
the goal is readable source you'd want to edit, not a lossless archive.

## Optional frontmatter fields

Beyond `title` and `author`:

```yaml
---
title: "On Simplicity"
author: "Jane Smith"
language: en              # default: en
publisher: "Tent Studios" # optional
date: 2026-04-30          # optional
isbn: "978-..."           # optional
description: |            # optional
  A short essay on what's
  essential.
cover: "cover.jpg"        # optional override
---
```

See [the full spec](../spec/prosedown.md) for everything.

## What ProseDown is *not* for

- Fixed-layout books / picture books / comics → use [Sigil](https://sigil-ebook.com/) or [Vellum](https://vellum.pub/)
- Poetry with line-level control → [Pandoc](https://pandoc.org/)
- Academic citations → [Pandoc with citeproc](https://pandoc.org/) or [LaTeX](https://www.latex-project.org/)
- PDF output → [Pandoc](https://pandoc.org/) or [LaTeX](https://www.latex-project.org/)

These are scope boundaries, not limitations to fix. If your book needs
something on this list, you need a different tool.
