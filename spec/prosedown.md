# The ProseDown Specification

**Version 0.6.1**
**Date: 2026-04-30**

ProseDown is a format for writing books in Markdown and compiling them into [EPUB](https://www.w3.org/TR/epub-33/) — the open standard for digital books used by Apple Books, Kobo, Google Play Books, and most e-readers. Moreover, EPUBs can be sent to Kindle readers through Amazon’s “[Send to Kindle](https://www.amazon.com/gp/sendtokindle)” service. This makes EPUBs the preferred format for prose-style reading content.

Like [Fountain](https://fountain.io/) is for screenplays, ProseDown is for ebooks: plain text that compiles to a complex format. Write in [Markdown](https://commonmark.org/). Add two lines of metadata. Compile. You have a valid, professional ebook.

A ProseDown project is just `.md` files with YAML frontmatter. Open them in any editor — [Obsidian](https://obsidian.md/), VS Code, iA Writer, TextEdit, or Notepad. Nothing is locked up, nothing is proprietary.

### Design Principles

1. **One file is enough.** A single `.md` file with frontmatter is a valid ProseDown project. *Because the barrier to entry should be zero.*

2. **Convention over configuration.** Cover auto-detected. CSS auto-detected. Chapters ordered by filename. *Because authors shouldn't configure what can be inferred.*

3. **Standard everything.** CommonMark Markdown. Standard YAML frontmatter. No custom syntax. *Because lock-in is the enemy of adoption, and your files should outlive any single tool.*

4. **Two directions.** Any ProseDown project compiles to a valid EPUB. Most reflowable EPUBs can be deconstructed to a ProseDown project (best-effort, with documented normalization). *Because authors need to work with existing books, not just create new ones. Building is the primary use case — stable and deterministic. Deconstruction is a practical tool, not a lossless archive.*

5. **Non-destructive.** Opening a ProseDown project in Obsidian, Hugo, Jekyll, or any Markdown editor doesn't break anything. *Because a format that fights your other tools isn't a format worth adopting.*

### What ProseDown Is For (and Not For)

ProseDown is for **reflowable prose**: fiction, narrative non-fiction, essays, memoirs, how-to books, devotionals — anything that's primarily text and reads well on any screen size.

ProseDown is **not for**:

| Out of Scope | Why | Instead, Use |
|-------------|-----|--------------|
| **Fixed-layout EPUBs** | Markdown is reflowable by nature. Picture books and comics need pixel-perfect positioning. | [Sigil](https://sigil-ebook.com/), [Vellum](https://vellum.pub/) |
| **Poetry with line-level control** | Full verse semantics require `epub:type="z3998:verse"` and hanging indents. Not expressible in CommonMark. (Basic poetry using hard line breaks works.) | [Pandoc](https://pandoc.org/), [LaTeX](https://www.latex-project.org/) |
| **Drama formatting** | Cast lists and dialogue attribution need semantic table markup. | [Pandoc](https://pandoc.org/) |
| **Academic citations** | Bibliography generation requires a citation engine. | [Pandoc with citeproc](https://pandoc.org/), [LaTeX](https://www.latex-project.org/) |
| **Media overlays** | Audio-synced narration requires SMIL. Text-only format. | [DAISY tools](https://daisy.org/) |
| **DRM / encryption** | ProseDown handles unencrypted EPUBs only. | Your distributor handles DRM |
| **PDF output** | Different layout model. ProseDown produces EPUB. | [Pandoc](https://pandoc.org/), [LaTeX](https://www.latex-project.org/) |
| **Chapter numbering** | Presentation choice. Write numbers in headings or use CSS counters. | — |
| **Font embedding** | Not yet supported. Planned for a future version. | — |

These are scope boundaries, not limitations to fix. If your book needs something on this list, you need a different tool.

### A Note on Language

This spec uses **MUST**, **SHOULD**, and **MAY** per [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) when precision matters. A conforming compiler MUST produce [EPUB 3.3](https://www.w3.org/TR/epub-33/) output that passes [EPUBCheck](https://www.w3.org/publishing/epubcheck/) without errors. Most of the spec reads as a guide — the normative language appears where two compilers need to agree on exact behavior.

---

# Getting Started

## Quick Start

This is a valid ebook:

```markdown
---
title: "On Simplicity"
author: "Jane Smith"
---

# On Simplicity

The simplest things are often the most profound.

## The Case for Simplicity

When we strip away the unnecessary, what remains is essential.
```

Two lines of frontmatter. One Markdown file. Compile it. Valid EPUB 3.3.

Why only two required fields? EPUB requires a title, identifier, and language — but identifier is generated automatically and language defaults to English. Everything else is inferred or optional.

---

## Adding Chapters

When your book outgrows a single file, create a folder:

```
my-book/
├── book.md              <- metadata
├── 01-chapter-1.md
├── 02-chapter-2.md
└── 03-chapter-3.md
```

**book.md** holds the book's metadata:

```yaml
---
title: "The Mountain Trail"
author: "Jeff Alldridge"
---
```

Each chapter file is just Markdown:

```markdown
# The Trailhead

The parking lot was empty at five in the morning.
```

That's it. The compiler reads `book.md` for metadata, discovers chapter files by their numeric prefix, pulls titles from each file's first `# Heading`, and builds a valid EPUB with a table of contents.

### Why It Works This Way

**Numeric prefixes** (`01-`, `02-`, `03-`) sort correctly in every file browser and terminal. You see the book's structure at a glance. Gaps are fine — use `01-`, `05-`, `10-` to leave room for insertions. This is the same convention Bookdown, Standard Ebooks, and most writing workflows use.

**`book.md`** is excluded from the chapter list. It's the manifest, not a chapter. Its name says what it is — a book. Even though it's primarily frontmatter, it's still a markdown file for editor compatibility.

**Chapter titles** come from the first `# Heading` in each file. You only need a `title:` field in frontmatter if you want the TOC entry to differ from the visible heading.

### Project Detection

A ProseDown project is either:
- A **single `.md` file** containing the required frontmatter, or
- A **folder** that contains a `book.md` file with the required frontmatter

If the input is a file, the compiler MUST treat it as a single-file book. If the input is a directory containing `book.md`, the compiler MUST treat it as a multi-file project. If the input is a directory with no `book.md`, the compiler MUST report an error.

### File Discovery and Ordering

In automatic discovery mode (no `chapters:` list), the compiler discovers chapter files as follows:

1. Scan only the **project root** — not subdirectories.
2. Include only `.md` files whose filenames begin with one or more digits followed by a hyphen (pattern: `^\d+-`). Examples: `01-intro.md`, `2-chapter.md`, `001-prologue.md`.
3. Exclude `book.md`, hidden files (`.` prefix), and draft files (`_` prefix).
4. Sort by the **integer value** of the leading digit sequence — not lexicographically. `2-` sorts before `10-`.
5. For files whose numeric prefixes resolve to the same integer value (e.g., `1-` and `01-` both resolve to 1), the compiler MUST report an error.
6. Files without a numeric prefix (e.g., `notes.md`, `scratch.md`) SHOULD produce a warning and are excluded from the build.

Why numeric sort instead of lexicographic? Because an author who writes `1-`, `2-`, `10-` expects them in that order. Lexicographic sort would put `10-` before `2-`. Compilers SHOULD recommend zero-padded prefixes (`01-` not `1-`) in warnings but MUST handle unpadded prefixes correctly.

All source files MUST be UTF-8.

---

## Adding Structure

Most books need more than just chapters. Here's a full project:

```
my-book/
├── book.md
├── cover.jpg
├── 00-copyright.md
├── 01-dedication.md
├── 02-part-1.md
├── 03-the-beginning.md
├── 04-the-middle.md
├── 05-part-2.md
├── 06-the-turning.md
├── 07-the-end.md
├── 08-about-the-author.md
├── _09-deleted-scene.md     <- draft, excluded from build
├── css/
│   └── style.css
└── images/
    └── map.png
```

### Chapter Roles

Not every file is a standard chapter. Copyright pages, dedications, and appendices have different roles in the book's structure. The `role:` field in frontmatter defines this:

```yaml
---
role: frontmatter
---

# Copyright

Copyright 2026 Jeff Alldridge. All rights reserved.
```

| Role | What it means | In the TOC? | EPUB mapping |
|------|--------------|-------------|--------------|
| `chapter` | Standard chapter (the default) | Yes | `epub:type="chapter"`, `role="doc-chapter"` |
| `frontmatter` | Copyright, dedication, foreword, preface | No (unless `toc: true`) | `epub:type="frontmatter"` |
| `backmatter` | Appendix, bibliography, about author | Yes | `epub:type="backmatter"` |
| `part` | Part title / divider page | Yes, as a section header | `epub:type="part"`, `role="doc-part"` |

Why `role:` and not `type:`? Because Hugo and Quarto both reserve `type:` for their own template systems. A ProseDown file with `type: frontmatter` would break a Hugo build. `role:` is unused by any major Markdown tool and says exactly what it means — this file's role in the book.

### TOC Override

By default, `frontmatter` files are excluded from the table of contents. But some frontmatter — a foreword, an introduction, a prologue — should be in the TOC. Use `toc:` to override:

```yaml
---
role: frontmatter
toc: true
---

# Foreword

When I first met the author...
```

The `toc:` field accepts `true` or `false` and overrides the role's default behavior. You can also use it to hide a chapter from the TOC: `toc: false` on a `chapter` role.

### Automatic Role Detection

Most of the time you don't need `role:` at all. The compiler detects roles from filenames:

| Filename slug | Detected role |
|--------------|---------------|
| `copyright` | frontmatter |
| `dedication` | frontmatter |
| `acknowledgments` / `acknowledgements` | frontmatter |
| `foreword`, `preface` | frontmatter |
| `epigraph`, `prologue` | frontmatter |
| `appendix`, `bibliography`, `glossary` | backmatter |
| `about-the-author`, `colophon`, `afterword`, `epilogue` | backmatter |
| `part-N` (where N is one or more digits) | part |
| Everything else | chapter |

**Matching rules**: The slug is the filename with the numeric prefix and extension removed (e.g., `03-about-the-author.md` → `about-the-author`). Slugs are compared **case-insensitively** after replacing underscores with hyphens. The match must be **exact** — substring matching is not used. `03-the-copyright-war.md` is a chapter because its slug is `the-copyright-war`, which is not in the table.

Explicit `role:` in frontmatter always overrides filename detection.

**Additional slugs recognized during deconstruction** (these appear in real EPUBs but are less common in author-created projects):

| Slug | Role |
|------|------|
| `titlepage`, `halftitlepage` | frontmatter |
| `endnotes` | backmatter |
| `table-of-contents`, `toc` | frontmatter |

Note: role auto-detection uses English-language slugs only. Authors writing in other languages SHOULD use explicit `role:` in frontmatter. This is a known limitation.

### Parts and Nesting

When a file has `role: part`, subsequent files nest under that part in the table of contents until the next part appears. Frontmatter files before the first part and backmatter files after the last part remain at the top level of the TOC.

```
Part One: The Ascent          <- 02-part-1.md (role: part)
  The Beginning               <- 03-the-beginning.md
  The Middle                  <- 04-the-middle.md
Part Two: The Descent         <- 05-part-2.md (role: part)
  The Turning                 <- 06-the-turning.md
  The End                     <- 07-the-end.md
```

Part files MAY have body content beyond the heading (an epigraph, a short introduction). This content is rendered as a part title page.

### Drafts and Excluded Files

Files with an underscore prefix (`_`) are excluded from compilation:

```
_09-deleted-scene.md     <- excluded
_notes.md                <- excluded
09-deleted-scene.md      <- included (remove _ when ready)
```

Why underscore? Because it's a familiar convention (Jekyll, Hugo, Sass all use it for "don't process this") and it's visible in file listings. Rename to remove the underscore when the file is ready for the book.

### What Gets Ignored

ProseDown compilers MUST ignore:
- Hidden files and directories (`.` prefix) — `.obsidian/`, `.git/`, `.DS_Store`
- Draft files (`_` prefix) — `_notes.md`, `_03-deleted-scene.md`
- `book.md` (it's the manifest, not a chapter)
- Non-Markdown files (except covers, CSS, and images)
- Subdirectories not matching known conventions (`css/`, `images/`)

Why? Because a ProseDown project, an Obsidian vault, and a Git repository can all be the same folder. They should never interfere with each other.

### Asset Conventions

| Asset | Convention | Override |
|-------|-----------|---------|
| **Cover** | `cover.jpg` at root (also `.jpeg`, `.png`, `.webp` — first match in that order) | `cover:` in frontmatter |
| **CSS** | `css/style.css` at root | `css:` in frontmatter |
| **Images** | `images/` directory, relative paths in Markdown | Standard `![alt](path)` syntax |

Why auto-detection instead of requiring explicit paths? Because `cover: cover.jpg` is redundant when the file is sitting right there. Convention over configuration means the obvious case requires zero configuration. The frontmatter override exists for the non-obvious case.

Cover SHOULD be at least 1600×2560 pixels for retail distribution. Compilers SHOULD warn on covers below 1400px on the long edge.

---

## book.md in Detail

`book.md` is the heart of a multi-file project. Its frontmatter defines the book's metadata. Its body content, if present, is the first thing readers see.

### Body Content

If `book.md` has body content in a multi-file project, it's rendered as the opening content — before all chapter files. This is the natural place for a short introduction, author's note, or book description.

```yaml
---
title: "The Mountain Trail"
author: "Jeff Alldridge"
---

This is a story about finding yourself in the Idaho backcountry.
It began as a journal and became something more.
```

The body is treated as `role: frontmatter` and appears before `00-` files in reading order. As frontmatter, it is excluded from the TOC by default. If the body is empty or absent, nothing is generated — the book starts with the first chapter file.

This is bidirectional — when deconstructing an EPUB, a book's introductory content or description page maps to book.md's body.

### Required Metadata

| Field | Type | Maps to | Notes |
|-------|------|---------|-------|
| `title` | string | `dc:title` | The book's title. MUST be present. |
| `author` | string or list | `dc:creator` | Author name(s). MUST be present. |

Missing required fields MUST produce an error. The compiler MUST NOT fall back to defaults for `title` or `author`.

`language` defaults to `en` (English) when not specified. Most books are in English, and requiring authors to type `language: en` on every project adds friction without value. Non-English authors set it explicitly — `language: fr`, `language: es-MX`, etc.

### Optional Metadata

None of these are required. Add them as your book matures toward publication.

#### Publishing essentials

Most authors preparing for retail distribution start here:

| Field | Type | Maps to | What it's for |
|-------|------|---------|---------------|
| `language` | string | `dc:language` | BCP 47 code. Default: `en` |
| `date` | string | `dc:date` | Publication date — `"2026"` or `"2026-04-07"` (quote years to prevent YAML integer parsing) |
| `publisher` | string | `dc:publisher` | Required by most retailers |
| `isbn` | string | `dc:identifier` | Emitted as `urn:isbn:...`. Included alongside the primary identifier. |
| `subject` | string or list | `dc:subject` | Genre/category (free-form — retailers map to their own taxonomies) |
| `description` | string | `dc:description` | Short blurb for catalogs. Body content is the long description. |
| `rights` | string | `dc:rights` | Copyright statement |

#### Discoverability and cataloging

These help with storefronts, library systems, and multi-contributor works:

| Field | Type | Maps to | What it's for |
|-------|------|---------|---------------|
| `subtitle` | string | `dc:title` refinement | Displayed below the title |
| `author-sort` | string | `file-as` on creator | "Last, First" for library sorting |
| `identifier` | string | `dc:identifier` | Explicit stable identifier. If absent, deterministic UUID is generated. |
| `series.name` | string | `belongs-to-collection` | Series grouping on storefronts |
| `series.number` | number | `group-position` | Position in series. Decimals allowed (e.g., `1.5` for a novella between books). |
| `editor` | string or list | `dc:creator` (role: edt) | |
| `translator` | string or list | `dc:creator` (role: trl) | |
| `illustrator` | string or list | `dc:creator` (role: ill) | |

#### Compiler overrides

These override auto-detected defaults. Most authors never need them:

| Field | Type | Maps to | What it's for |
|-------|------|---------|---------------|
| `cover` | path | `cover-image` property | Overrides auto-detection |
| `css` | path | stylesheet link | Overrides auto-detection |
| `direction` | string | `page-progression-direction` | `ltr`, `rtl`, or `default`. Default: `default` |
| `toc-depth` | integer | nav structure | How many heading levels appear in TOC (default: 2 multi-file, 1 single-file) |
| `chapters` | list | spine order | Explicit file order (overrides filesystem). See below. |
| `accessibility` | object | schema.org properties | See Accessibility section |

### Identifier and UUID

Every EPUB needs a unique, stable identifier. ProseDown handles this automatically:

- If `identifier:` is present, the compiler uses it as the primary `dc:identifier` (the OPF `unique-identifier`).
- If `isbn:` is present but `identifier:` is not, the ISBN becomes the primary identifier (emitted as `urn:isbn:...`).
- If neither is present, the compiler generates a **deterministic UUID** using UUIDv5: SHA-1 hash of the normalized string `title|author|language` against the fixed ProseDown namespace UUID `a0b1c2d3-e4f5-6789-abcd-ef0123456789`.

Why deterministic? Because a random UUID on every build makes retail storefronts treat each compilation as a new book — losing reviews, sales rank, and reading progress. Same inputs MUST produce the same UUID across all conforming compilers.

Why an explicit `identifier:` field? Because if you fix a typo in your title, the deterministic UUID changes. `identifier:` lets you pin a stable ID that survives metadata edits.

### Multiple Authors

```yaml
author:
  - "Jane Smith"
  - "John Doe"
```

Why a simple list instead of structured objects with roles? Because most books have one or two authors. The `editor`, `translator`, and `illustrator` fields handle the common contributor roles. For the rare case of complex role assignments, use Pandoc or hand-edit the OPF.

### Series

```yaml
series:
  name: "The Adventure Trilogy"
  number: 1
```

Why does this matter? Amazon KDP and Apple Books use series metadata to group books on storefronts. Without `belongs-to-collection` and `group-position` in the OPF, your trilogy appears as three unrelated titles. `series.number` accepts decimals — `1.5` for a novella between books is common practice.

### Explicit Chapter Order

```yaml
chapters:
  - prologue.md
  - the-beginning.md
  - the-end.md
```

When `chapters:` is present:
- Only listed files are included, in listed order. Filesystem sorting is ignored.
- Files do NOT need numeric prefixes.
- Filename-based role detection still applies.
- `chapters:` MAY reference files in subdirectories (e.g., `parts/01-intro.md`).
- `book.md` MUST NOT appear in the list.
- A listed file that doesn't exist MUST produce an error.
- Duplicate entries MUST produce an error.
- Hidden files (`.` prefix) or draft files (`_` prefix) in the list MUST produce an error. Explicit listing does not override exclusion rules — if you want a draft in the build, remove the underscore.
- Unlisted `.md` files in the project root SHOULD produce a warning.

Why offer this? Because numeric prefix ordering breaks down when you frequently reorder chapters or work with files that don't have prefixes. This gives you mdBook/Quarto-style explicit control when you need it, without requiring it when you don't.

### Chapter-Level Frontmatter

Chapters support these frontmatter fields:

| Field | What it does |
|-------|-------------|
| `title` | Override the heading-derived title for TOC |
| `author` | Override book-level author for this chapter (anthologies) |
| `role` | Override auto-detected role |
| `toc` | Override whether this chapter appears in TOC (`true` / `false`) |
| `language` | Override book-level language for this chapter (sets `xml:lang` on the content document) |

Chapter-level `language` affects smart typography for that chapter (e.g., French quotes in a French chapter within an English book). For inline language changes within a chapter (a French quotation inside English prose), use raw HTML: `<span lang="fr">«Bonjour»</span>`.

All other frontmatter fields on chapters are ignored by ProseDown but preserved for other tools (Obsidian's `tags`, Hugo's `layout`, etc.).

### Chapter-Level Author

In anthologies or collections with multiple contributors, chapters can override the book's author:

```yaml
---
title: "The View from Here"
author: "Guest Writer"
---
```

A chapter's `author:` overrides the book-level author for that chapter only. Chapter-level authors are added to the OPF as additional `dc:creator` elements so they're discoverable in retail search. This enables compilations, essay collections, and multi-author works without complex metadata.

---

# Writing in ProseDown

## Markdown

**ProseDown Markdown profile**: [CommonMark](https://commonmark.org/) core plus footnotes, tables, and definition lists.

A conforming compiler MUST support:
- CommonMark core syntax
- Footnotes (`[^1]` and `[^1]:` block definitions)
- Pipe tables (GFM-style)
- Definition lists (`: ` definition syntax)

A compiler MAY support additional extensions internally but MUST NOT require them for valid ProseDown input.

Why CommonMark and not MultiMarkdown or Pandoc Markdown? Because CommonMark is the universal baseline — it's what Obsidian, Hugo, GitHub, VS Code, and every modern tool speaks. MultiMarkdown has great features but a tiny ecosystem. Pandoc Markdown includes dozens of extensions that vary by version. We add only the extensions that books genuinely need and that pass the classless CSS test: if classless CSS can make it pretty from Markdown to HTML, it belongs.

### Footnotes

```markdown
This claim needs a source.[^1]

[^1]: See Smith, 2024, p. 42.
```

Compiled to EPUB footnotes with `epub:type="footnote"`, `role="doc-footnote"`, and bidirectional linking (`epub:type="noteref"`, `role="doc-noteref"`). Reading apps that support it show these as pop-up notes. Footnotes render at the end of the **chapter**, not the end of the book.

Why include footnotes when they're technically an extension? Because books need footnotes. The `[^1]` syntax is supported by Pandoc, Obsidian, Hugo, Jekyll (via Kramdown), GitHub, and most modern Markdown parsers. Leaving this out would make ProseDown unusable for non-fiction.

### Tables

```markdown
| Column A | Column B |
|----------|----------|
| Value 1  | Value 2  |
```

Compiled to `<table>`. Keep tables simple — EPUB is reflowable, and wide tables overflow on small screens.

### Definition Lists

```markdown
Protagonist
: The main character of a story

Antagonist
: A character who opposes the protagonist
```

Compiled to `<dl>`, `<dt>`, `<dd>`. Essential for glossaries — common in non-fiction.

Why include definition lists? Because glossaries are common in non-fiction books, and the `<dl>`/`<dt>`/`<dd>` HTML elements map naturally to EPUB content. This extension is supported by Pandoc, PHP Markdown Extra, Kramdown, and most serious Markdown processors.

### Image Captions

Standard Markdown images with a title attribute become captioned figures:

```markdown
![A map of the Sawtooth Mountains](images/map.png "The Sawtooth Range from Redfish Lake")
```

Compiled to:

```html
<figure>
  <img src="images/map.png" alt="A map of the Sawtooth Mountains" />
  <figcaption>The Sawtooth Range from Redfish Lake</figcaption>
</figure>
```

The compiler MUST strip the `title` attribute from the `<img>` element in the output — the caption lives in `<figcaption>` only. Why? Because the `title` attribute renders as a tooltip that's invisible on touch screens and confuses screen readers when both `title` and `<figcaption>` are present.

Images without title text compile to plain `<img>` tags. No new syntax — this uses the existing, underused title attribute. And `<figure>` + `<figcaption>` is exactly what classless CSS already makes beautiful.

Images MUST have an `alt` attribute. Informative images SHOULD have meaningful, non-empty alt text. Decorative images MAY use empty alt (`alt=""`). Compilers SHOULD warn when `alt` is missing and MAY warn when `alt` is empty. Remote URLs (`https://...`) MUST produce an error — EPUBs require all assets to be local. All images MUST be inside the project directory.

### Raw HTML

CommonMark allows raw HTML in Markdown. ProseDown preserves it.

Raw HTML is passed through to the EPUB output, normalized to well-formed XHTML (self-closing void elements, lowercase tags, quoted attributes). This is the escape hatch for the 5% of cases Markdown can't express — verse numbers, small caps, semantic spans, scripture formatting.

```markdown
The verse says: <sup>16</sup> For God so loved the world...
```

Why allow it? Because raw HTML is *already part of CommonMark* — accepting it isn't adding an extension, it's refusing to subtract one. Your files still render in every Markdown previewer. And it means ProseDown doesn't need to invent syntax for superscripts, abbreviations, or semantic markup.

**Sanitization rules** — compilers MUST:
- Strip `<script>` elements entirely
- Strip event-handler attributes (`onclick`, `onload`, etc.)
- Report an error on external resource references (`<img src="https://...">`, `<link href="https://...">`) — EPUBs must be self-contained

Compilers SHOULD preserve all other raw HTML that normalizes to valid XHTML. Inline styles MAY be preserved but are discouraged.

If an author injects ARIA roles in raw HTML, the compiler MUST preserve them — author-declared accessibility attributes take precedence over auto-generated ones.

### Scene Breaks

Use Markdown horizontal rules to mark scene breaks or section transitions within a chapter. `---`, `***`, and `___` all work. The default stylesheet renders them as spaced ornaments (like `* * *`), not visible lines.

Note: `---` after the opening frontmatter block is always treated as a scene break (`<hr>`), not as a YAML delimiter. The YAML frontmatter block is delimited by the first `---`/`---` pair at the very start of the file only.

### Cross-File Links

Link to other chapters in your book using standard Markdown links with relative paths:

```markdown
As discussed in [Chapter 2](02-chapter-2.md), the trail continues.

See [the summit section](03-chapter-3.md#the-summit) for details.
```

Rewritten to proper XHTML references during compilation. Fragment identifiers (`#heading-slug`) are supported — heading anchors are generated by slugifying heading text (lowercase, spaces to hyphens, strip punctuation).

Broken internal links (referencing project files or in-publication anchors that don't exist) MUST produce an error.

Obsidian-style wikilinks (`[[Chapter 2]]`) are not part of the ProseDown Markdown profile. If you author in [Obsidian](https://obsidian.md/), set it to use standard Markdown links (Settings > Files & Links > Use `[[Wikilinks]]` → off). This is a one-time setting change.

### Chapter Numbers

ProseDown does not generate chapter numbers. Authors who want them write them into the heading (`# Chapter 1: The Trailhead`) or use CSS counters in a custom stylesheet. Why? Because numbering is a presentation choice, and many books (especially fiction) use titled chapters without numbers.

### What ProseDown Doesn't Add

No fenced divs. No attribute syntax. No `{.class}` markers. No custom Markdown extensions.

Why? Because every custom extension is a portability tax. Your ProseDown files render correctly in any Markdown previewer, any static site generator, and any text editor. The moment we add `:::` divs, we break that promise.

The combination of raw HTML (for edge cases) and classless CSS (for core content) gives you semantic richness without inventing syntax.

---

# How the EPUB Gets Made

## Build-Time Features

These happen automatically when your project compiles to EPUB. You don't need to do anything — the compiler handles it.

### Smart Typography

| You type | EPUB output |
|----------|-------------|
| `"text"` | \u201ctext\u201d (curly double quotes) |
| `'text'` | \u2018text\u2019 (curly single quotes) |
| `--` | \u2013 (en-dash) |
| `---` | \u2014 (em-dash) |
| `...` | \u2026 (ellipsis) |

Smart typography applies to **prose text nodes after Markdown parsing** — not to raw source text.

Why not require authors to type Unicode characters? Because straight quotes are what every keyboard produces, and asking authors to manually insert curly quotes is tedious. But straight quotes in a published ebook look amateur. Standard Ebooks solves this with their `se typogrify` build step. ProseDown does the same — source stays clean, output is polished.

**Exclusion rules** — smart typography MUST NOT apply inside:
- Fenced code blocks and inline code (backticks)
- URLs and autolinks
- HTML tags and attributes
- YAML frontmatter values

**Already-typeset text**: If the source already contains curly quotes or proper em-dashes (the author typed Unicode), the compiler MUST NOT double-convert them.

**Apostrophes and edge cases**:

| Input | Output | Rule |
|-------|--------|------|
| `'tis` | \u2019tis | Word-initial apostrophe → right single quote |
| `'90s` | \u201990s | Decade abbreviation → right single quote |
| `rock 'n' roll` | rock \u2019n\u2019 roll | Mid-word apostrophes → right single quote |
| `5' 10"` | 5\u2032 10\u2033 | Primes (feet/inches) → prime/double-prime if detectable, otherwise unchanged |
| `"nested 'quotes' here"` | \u201cnested \u2018quotes\u2019 here\u201d | Nested quotes alternate double/single |
| Already-curly `\u201ctext\u201d` | \u201ctext\u201d | No double-conversion |
| `don't` | don\u2019t | Contraction → right single quote |

**Language-aware quotes**: The `language:` field determines quote style. English uses \u201c...\u201d and \u2018...\u2019. French uses \u00ab...\u00bb. German uses \u201e...\u201c. If a compiler doesn't support a language's quote style, it SHOULD warn and fall back to English-style curly quotes.

### Table of Contents Generation

The `toc-depth` field controls how many heading levels appear in the EPUB's navigation:

| `toc-depth` | What appears in the TOC |
|-------------|------------------------|
| `0` | Book title only — no chapter or heading entries |
| `1` | Chapter titles (`#` headings) only |
| `2` (default) | Chapter titles + `##` headings |
| `3` | Chapter titles + `##` + `###` headings |

**Defaults**: Multi-file books default to `toc-depth: 2`. Single-file books default to `toc-depth: 1`.

When `toc-depth` is 1 or higher, each chapter's first `#` heading appears as a top-level TOC entry. Sub-headings appear as nested entries up to the specified depth. When `toc-depth` is 0, the TOC contains only the book title — no chapter entries are generated. A chapter file SHOULD NOT contain more than one level-1 heading (`#`). The compiler MUST use only the first `#` heading for the chapter title and TOC entry, and MUST report any additional `#` headings as a warning.

### Title and Heading Deduplication

If a chapter has both `title:` in frontmatter and a first `# Heading`:

- **They match** (case-sensitive, compared before smart typography, after whitespace trimming): The compiler uses the heading as the rendered content and the TOC entry. The heading remains in the DOM — it is NOT removed. No duplicate is generated because only one source is used.
- **They differ**: The frontmatter `title:` is used for the TOC. The `# Heading` renders in the body as written. Both are preserved.
- **No `# Heading` exists**: The frontmatter `title:` is used for the TOC. The compiler SHOULD generate a heading element in the output for structural integrity.
- **No frontmatter `title:` and no `# Heading`**: The title is derived from the de-slugified filename (e.g., `03-the-summit.md` → "The Summit").

### Modified Timestamp

EPUB requires exactly one `dcterms:modified` timestamp. For reproducible builds, the compiler SHOULD derive this from the most recent modification time of any source file in the project. If source mtimes are unavailable, the compiler MAY use the current UTC time.

Why reproducible? Because two compilations of identical source should produce identical EPUBs. Random timestamps break CI artifact comparison, content-addressed storage, and "did anything actually change?" workflows.

### Default Stylesheet

If no custom CSS is provided, the compiler uses a built-in stylesheet designed for books:
- Clean, readable serif typography
- First-line paragraph indentation (no indent after headings or breaks)
- Centered chapter titles with spacing
- Scene breaks (horizontal rules as spaced ornaments, not lines)
- `<figure>` and `<figcaption>` styling
- `<dl>` / `<dt>` / `<dd>` for glossaries
- `<blockquote>` styling
- Dark mode via `prefers-color-scheme`
- Responsive for phones, tablets, and e-ink

The default stylesheet MUST use CSS logical properties (`margin-inline-start`, `padding-block-end`) instead of physical properties (`margin-left`, `padding-bottom`). Why? Because physical properties break in RTL languages — `margin-left` indents the wrong side of Arabic text. Logical properties adapt automatically to reading direction.

The default stylesheet SHOULD be designed around CSS custom properties (`:root { --body-font: ...; }`) so that authors who export and customize it can retheme by changing a few variables at the top.

Why opinionated defaults? Because the #1 complaint about Pandoc and Calibre is that output looks "serviceable, not polished." Standard Ebooks proves good CSS is the difference between amateur and professional. Authors want beautiful output without writing CSS.

**Custom CSS replaces the default entirely.** If `css/style.css` is present (or `css:` specifies a file), the compiler MUST NOT include the default stylesheet. This is a full replacement, not an additive cascade. Why? Because CSS cascade debugging is painful, and "my styles plus mysterious defaults" is harder to reason about than "my styles, period."

Compilers SHOULD offer a way to export the default stylesheet as a starting point (e.g., `prosedown init css`), so authors who want to change one font don't have to start from scratch.

---

# Working with Existing EPUBs

## Deconstructing an EPUB

ProseDown has two directions with two different promises:

**Building** (Markdown → EPUB) is the primary use case. It's stable, reproducible, and deterministic. Same source, same output. This is what ProseDown is for.

**Deconstructing** (EPUB → Markdown) is best-effort with documented normalization. The goal is to produce readable Markdown that an author would want to work with — not to perfectly preserve every EPUB-specific artifact.

Why the asymmetry? Because perfect round-trip fidelity would require encoding EPUB-specific structures (title pages, imprint pages, navigation landmarks, vendor metadata) in the Markdown files, making them unreadable. ProseDown optimizes for human-readable source files, which means deconstruction normalizes EPUB structures into ProseDown conventions.

### How Deconstruction Works

1. Unzip the EPUB archive
2. Parse OPF metadata → `book.md` frontmatter
3. Read spine order → numeric file prefixes (`00-`, `01-`, `02-`)
4. Convert each XHTML content document → Markdown
5. Extract cover image → root (original format preserved)
6. Extract CSS → `css/style.css` (if custom styles exist; multiple source stylesheets are concatenated in OPF manifest order into one file)
7. Extract images → `images/`, rewrite paths
8. Detect chapter roles from `epub:type` → set `role:` in frontmatter
9. Emit explicit `title:` and `role:` in chapter frontmatter when detected

Filenames are generated per the Deconstruction Filename Generation algorithm in Part 5 (Reference).

Compilers SHOULD emit a summary of what was preserved, approximated, and dropped.

### Missing Required Metadata

Source EPUBs may lack metadata that ProseDown requires for building (`title`, `author`). When deconstructing:

- Missing `title`: derive from the first content document's heading, or the EPUB filename. Emit a warning.
- Missing `author`: emit `author: "Unknown"` and a warning. The deconstructed project remains buildable.
- Missing `language`: default to `en` (same as build behavior).

Why? Because deconstruction should always produce a buildable project. Google Docs exports and many legacy EPUBs omit creator metadata entirely. Erroring on deconstruction defeats the purpose — the author can fix the metadata after extraction.

### What's Preserved

Text content, headings, lists, emphasis, links, images, code blocks, blockquotes, tables, footnotes, and core metadata (title, author, language, publisher, date, ISBN, rights, subjects, series).

### What's Normalized

| EPUB Feature | ProseDown Normalization |
|-------------|------------------------|
| Title pages | Collapsed into `book.md` body content or a frontmatter file (see below) |
| Imprint / colophon pages | Normalized to standard slug-named files |
| Navigation documents | Regenerated from chapter structure (not preserved as files) |
| Vendor-specific metadata | Dropped (Calibre tags, iBooks properties, etc.) |
| Inline CSS / class-heavy markup | Flattened to clean Markdown |
| Duplicate structural wrappers | Simplified to single heading + content |
| Internal fragment links | Preserved when target maps to a heading slug; dropped when target ID doesn't survive Markdown normalization |

### Title Page Identification

Title pages are the biggest source of round-trip drift in real EPUBs. Many EPUBs contain a dedicated title page document that doesn't exist as a concept in ProseDown (authors don't write title pages — the compiler generates them). During deconstruction, the compiler MUST identify and normalize title pages rather than emitting them as regular chapters.

A content document is identified as a title page when **any** of these conditions are true (checked in order):

1. It has `epub:type="titlepage"` or `epub:type="halftitlepage"`
2. Its filename slug matches `titlepage` or `halftitlepage` (per the standard slug comparison rules)
3. Its only substantive content is the book's title and/or author name — no prose paragraphs, no other headings

When a title page is identified:

- If it contains only the title and author (the common case), it is **dropped** — the compiler already generates this from `book.md` frontmatter.
- If it contains additional content (a dedication, epigraph, or introductory paragraph beyond title/author), that content is **collapsed into `book.md` body content**.
- The deconstructed output MUST emit `role: frontmatter` in the frontmatter of any file derived from a title page that isn't dropped entirely.

Why this matters: without these heuristics, a round-trip (EPUB → MD → EPUB → MD) produces a duplicate title page on each pass — the deconstructed title page file plus the compiler-generated one. This is the drift pattern the CLI audit identified as the most disruptive.

### Internal Link Normalization

Source EPUBs contain internal links to HTML `id` attributes that may not survive conversion to Markdown. During deconstruction:

- Links to other content documents (e.g., `chapter-2.xhtml`) are rewritten to Markdown links (`02-chapter-2.md`).
- Fragment links (e.g., `#section-3`) are preserved when the target maps to a heading slug that the canonical slug algorithm would generate.
- Fragment links to IDs that don't map to heading slugs (custom IDs, span targets, vendor-generated anchors) SHOULD be dropped. Compilers MAY warn.
- Unresolvable local links (pointing to files not in the spine) SHOULD be dropped rather than emitting broken Markdown links.

Why drop rather than preserve? Because broken links in a deconstructed project would cause build errors on the next compile. Best-effort normalization means the output must be buildable.

This means the first decompilation is the "canonical" ProseDown form. Rebuilding and decompiling again (EPUB → MD → EPUB → MD) may produce slightly different filenames or ordering — this is expected normalization, not a bug.

### What's Lost

| Feature | Why it's lost |
|---------|--------------|
| Fine-grained `epub:type` | Structural roles preserved; epigraph/colophon/etc. flatten to plain content |
| Pop-up footnote behavior | Reading-app-specific. Footnotes preserved as `[^1]` syntax. |
| Page break markers | No Markdown equivalent |
| Landmarks / page-list | Navigation beyond TOC not preserved |
| Media overlays | Audio sync is out of scope |
| Fixed-layout properties | ProseDown is reflowable only |
| Font embedding | Not supported in this version |

### What's NOT Supported for Deconstruction

Fixed-layout EPUBs, DRM-encrypted EPUBs, and EPUBs with heavy scripting are outside ProseDown's scope. A compiler SHOULD detect these and report an error rather than produce a degraded result.

---

# Implementation Reference

This section is for people building ProseDown compilers or tools. Authors can skip it — everything above is what you need to write books.

## EPUB Mapping

| ProseDown | EPUB 3.3 Element | Notes |
|-----------|-----------------|-------|
| `title` | `dc:title` | Required |
| `author` | `dc:creator` (role: aut) | Required. Multiple → multiple elements. |
| `language` | `dc:language` | Default: `en`. BCP 47. |
| `subtitle` | `dc:title` refinement | `title-type: subtitle` |
| `author-sort` | `meta` refinement with `property="file-as"` | Refines the first `dc:creator` element |
| `date` | `dc:date` | YYYY or YYYY-MM-DD |
| `identifier` | `dc:identifier` | Primary package identifier |
| `publisher` | `dc:publisher` | |
| `description` | `dc:description` | Short form. book.md body is long form. |
| `isbn` | `dc:identifier` | Emitted as `urn:isbn:...` alongside primary identifier |
| `rights` | `dc:rights` | |
| `subject` | `dc:subject` | One element per subject |
| `series.name` | `belongs-to-collection` | Plus `collection-type: series` |
| `series.number` | `group-position` | Refines the collection. Decimals allowed. |
| `cover` | `cover-image` property | |
| `direction` | `page-progression-direction` | On spine element |
| `editor` | `dc:creator` (role: edt) | MARC relator |
| `translator` | `dc:creator` (role: trl) | MARC relator |
| `illustrator` | `dc:creator` (role: ill) | MARC relator |
| Chapter `role` | `epub:type` + DPUB-ARIA `role` | See Chapter Roles table |
| `accessibility` | schema.org properties | See Accessibility section |

### Auto-Generated at Export

| Element | How | Why |
|---------|-----|-----|
| `dc:identifier` | Deterministic UUIDv5 (or explicit `identifier:` / `isbn:`) | EPUB requires a unique identifier |
| `dcterms:modified` | Source file mtime (or current UTC) | EPUB requires exactly one, in `YYYY-MM-DDThh:mm:ssZ` format |
| `nav.xhtml` | Chapter titles + heading hierarchy | EPUB 3 requires a navigation document |
| `toc.ncx` | Same structure as nav | EPUB 3.3 deprecated `toc.ncx`, but many e-ink devices and older reading apps still require it. Compilers SHOULD generate it for maximum compatibility. Compilers MAY offer a flag to omit it. |
| Accessibility | Content analysis | Conservative factual defaults (see Accessibility) |

## Accessibility

EPUB accessibility is governed by [EPUB Accessibility 1.1](https://www.w3.org/TR/epub-a11y-11/) and the European Accessibility Act. Getting this wrong has legal and ethical implications.

### Default Behavior

When no `accessibility:` block is present, the compiler generates only metadata it can factually verify:

- `schema:accessMode`: `textual` (and `visual` if images are present)
- `schema:accessModeSufficient`: `textual`
- `schema:accessibilityFeature`: `readingOrder`, `structuralNavigation`, `tableOfContents`

The compiler MUST NOT auto-generate `dcterms:conformsTo`, `accessibilitySummary`, or `accessibilityHazard`. These are claims that require human judgment — the compiler can't verify that your alt text is meaningful, that your content has no hazards, or that it meets WCAG standards.

Why not auto-generate conformance claims? Because claiming WCAG 2.1 Level AA compliance without verification is a fraudulent accessibility claim. The European Accessibility Act makes this a legal risk. Honest, limited metadata is better than unverified claims.

### Explicit Accessibility Metadata

Authors who have verified their content's accessibility can declare it:

```yaml
accessibility:
  summary: "Reflowable text with alt text for all images and full structural navigation."
  conformsTo: "EPUB Accessibility 1.1 - WCAG 2.1 Level AA"
  features:
    - alternativeText
    - readingOrder
    - structuralNavigation
    - tableOfContents
  hazards:
    - none
```

When present, explicit values override their corresponding auto-generated defaults on a per-field basis. Fields not specified in the `accessibility:` block retain their auto-generated values.

### Author Guidance

- Images SHOULD have meaningful `alt` text. Empty alt (`![](img.png)`) is allowed for decorative images but compilers SHOULD warn.
- Heading levels SHOULD not be skipped (e.g., `#` to `###` with no `##`). Compilers SHOULD warn on skipped levels.
- The compiler guarantees structural navigation (TOC, heading hierarchy). The author is responsible for descriptive content quality.

## Canonical Algorithms

These algorithms MUST be implemented identically across all conforming compilers.

### Slug Generation

Used for heading anchors, filename generation, role matching, and cross-file link targets.

1. Apply Unicode NFC normalization
2. Convert to lowercase
3. Replace underscores with hyphens
4. Replace whitespace sequences with a single hyphen
5. Remove all characters that are not alphanumeric or hyphens
6. Collapse consecutive hyphens into one
7. Strip leading and trailing hyphens
8. If the result is empty, use `section`

For heading anchors within a file, duplicate slugs get a suffix: `-2`, `-3`, etc. Across files, `id` attributes are scoped to their content document — `chapter-1.xhtml#the-overview` and `chapter-2.xhtml#the-overview` are distinct because they live in different XHTML files. Cross-file links use the full path (`chapter-2.xhtml#the-overview`), not bare fragment IDs.

### Title Resolution

One canonical precedence order for chapter titles:

1. `title:` in chapter frontmatter — always wins
2. First `#` heading in the file body
3. De-slugified filename (e.g., `03-the-summit.md` → "The Summit")

If `title:` and the first `#` heading both exist and match (case-sensitive, before smart typography, after whitespace trimming), the heading remains in the DOM and is used for both TOC and rendering. If they differ, `title:` is used for the TOC and the heading renders in the body.

For `book.md` body content in multi-file mode: title comes from the body's first `#` heading. If none exists, the book's `title:` field is used.

For single-file books: the `title:` frontmatter field is the primary title. The first `#` heading in the body, if matching, is used for rendering.

### UUID Serialization

The deterministic UUIDv5 input string is formed by:

1. Trim whitespace from `title`, each `author` entry, and `language`
2. Apply NFC normalization to all values
3. If `author` is a list, join entries with `|` in YAML list order
4. Concatenate: `{title}|{author_string}|{language}`
5. Hash with SHA-1 against namespace `a0b1c2d3-e4f5-6789-abcd-ef0123456789`

Example: title `"The Mountain Trail"`, author `"Jeff Alldridge"`, language `"en"` → input string `The Mountain Trail|Jeff Alldridge|en`

### Empty Value Handling

| Condition | Behavior |
|-----------|----------|
| `title: ""` or `title:` (empty) | Error — title is required |
| `author: ""` or `author: []` | Error — author is required |
| Empty optional string field | Treated as absent — field is not emitted |
| `chapters: []` (empty list) | Treated as absent — fall back to auto-discovery |
| `accessibility: {}` | Treated as absent — auto-generate defaults |
| Whitespace-only values | Treated as empty after trimming |

### Path and Encoding Rules

- All source files MUST be UTF-8. BOM is allowed but SHOULD NOT be used.
- Line endings: LF or CRLF accepted, normalized to LF internally.
- NUL bytes in source files MUST produce an error.
- File paths MUST use forward slashes. Backslashes are normalized to forward slashes.
- `..` path segments MUST produce an error — files outside the project root are forbidden.
- Absolute paths MUST produce an error.
- Symlinks SHOULD be resolved; if they point outside the project root, compilers MUST produce an error.
- Case-sensitive matching is used for filenames. Compilers SHOULD warn when two files differ only by case.

### Footnote Scope

- Footnote labels (`[^1]`, `[^note]`) are scoped to their file. The same label may be used in different chapter files without collision.
- Numbering restarts per chapter in the output.
- Cross-file footnote references (a ref in one file targeting a definition in another) are not supported and SHOULD produce a warning.
- Duplicate labels within the same file MUST produce an error.

### Build Output Filenames

XHTML content document filenames in the EPUB are derived from the source Markdown filename:

1. Strip the numeric prefix and extension (e.g., `03-the-summit.md` → `the-summit`)
2. Slugify per the canonical slug algorithm
3. Append `.xhtml`
4. If two chapters would produce the same filename, append `-2`, `-3`, etc.
5. `book.md` body content (when present) uses the filename `book-intro.xhtml`
6. Single-file books use `content.xhtml`

This algorithm affects cross-file link rewriting — `.md` extensions become `.xhtml` using the same slug.

### EPUB Directory Layout

Compilers MUST use this internal EPUB structure:

```
book.epub
├── mimetype
├── META-INF/
│   └── container.xml
└── EPUB/
    ├── content.opf
    ├── css/
    │   └── style.css
    ├── images/
    │   └── (project images)
    └── text/
        ├── nav.xhtml
        ├── chapter-1.xhtml
        ├── chapter-2.xhtml
        └── ...
```

Content documents live in `EPUB/text/`. CSS lives in `EPUB/css/`. Images live in `EPUB/images/`. The navigation document (`nav.xhtml`) lives alongside content documents in `EPUB/text/`. Stylesheet references from content documents use `../css/style.css`.

### Deconstruction Filename Generation

Filenames are generated as `NNN-slug.md` where:
- `NNN` is a zero-padded spine index. Padding width is the greater of 2 and the number of digits needed for the total file count.
- The slug is determined by this precedence:
  1. If the document's `epub:type` maps to a known role slug (e.g., `copyright`, `dedication`, `colophon`, `titlepage`, `endnotes`, `toc`), use the role slug.
  2. Otherwise, use the chapter's first heading, slugified per the canonical algorithm.
  3. If no heading exists, use the source XHTML filename, slugified.
- Deconstructed files SHOULD include explicit `title:` and `role:` in frontmatter to support stable rebuilds.

Why role slugs first? Because `000-copyright.md` is more stable across round-trips than `000-copyright-2026-jane-smith-all-rights-reserved.md` derived from heading text. Known role pages should have predictable filenames.

---

## Errors and Warnings

A ProseDown compiler MUST classify issues as:

- **Error** — compilation fails, no EPUB produced
- **Warning** — compilation succeeds, but the author should review
- **Ignored** — no diagnostic required

### Errors

| Condition | Why it's fatal |
|-----------|---------------|
| Missing `title` or `author` | EPUB can't be valid without these |
| Malformed YAML frontmatter | Can't parse metadata |
| Duplicate numeric prefixes | Ambiguous chapter order |
| File listed in `chapters:` doesn't exist | Can't build the spine |
| Duplicate entry in `chapters:` | Ambiguous intent |
| `book.md` listed in `chapters:` | Manifest can't be a chapter |
| Remote image URL in Markdown | EPUB requires local assets |
| Broken internal links | Referencing files or anchors that don't exist |
| Invalid UTF-8 in source files | Can't produce valid XHTML |
| NUL bytes in source files | Can't produce valid content |
| Path traversal (`..` segments) | Files outside project root forbidden |

### Warnings

| Condition | What to tell the author |
|-----------|------------------------|
| Chapter with no `#` heading (title from filename) | "Title derived from filename — consider adding a heading" |
| Image missing alt text | "Missing alt text affects accessibility" |
| Unprefixed `.md` files ignored in auto mode | "File not included — add numeric prefix or list in chapters:" |
| Frontmatter `title:` and first `#` heading differ | "TOC uses frontmatter title; heading renders in body" |
| Cover image below recommended size | "Recommended minimum 1600×2560 for retail" |
| Skipped heading levels | "Heading jumps from H1 to H3 — affects accessibility" |
| Unsupported language for smart quotes | "Falling back to English-style quotes" |
| Unpadded numeric prefix | "Consider zero-padding: 01- instead of 1-" |
| Multiple `#` headings in one chapter file | "Only the first H1 is used; additional H1s are ignored" |

### Silently Ignored

- Hidden files and directories (`.` prefix)
- Draft files (`_` prefix)
- Unknown frontmatter fields on chapters
- Non-Markdown files outside recognized conventions

---

# Compatibility and Scope

## Compatibility

### With Markdown Tools

ProseDown files work in other tools because the frontmatter uses standard YAML fields that don't collide with other tools:

- **Obsidian** — reads `title`, `author`, `date`. Ignores `role`, `series`. Add Obsidian's `tags`, `aliases`, `cssclass` freely.
- **Hugo** — no conflicts. ProseDown uses `role:` (not `type:`, which Hugo reserves for template selection).
- **Jekyll** — no conflicts. `role:` is not a reserved Jekyll field.
- **Pandoc** — most fields map directly. `author` maps to `dc:creator`, `series.name` maps to `belongs-to-collection`. ProseDown files can serve as Pandoc input with minimal adjustment.
- **Quarto** — no conflicts. ProseDown uses `role:` (not `type:`, which Quarto reserves for EPUB TypesRegistry).

**ProseDown ignores fields it doesn't recognize.** You can freely add tool-specific metadata without affecting compilation. A file can be a valid ProseDown chapter, an Obsidian note, and a Hugo content page simultaneously.

### With Obsidian Vaults

A ProseDown project can live inside an Obsidian vault. The compiler ignores `.obsidian/` and all hidden directories. However:

- **Wikilinks** (`[[Chapter 2]]`) are not ProseDown-compatible. Set Obsidian to use standard Markdown links (Settings > Files & Links > Use `[[Wikilinks]]` → off).
- **Nested YAML** in Obsidian's Properties UI has limited support for complex structures like `series:`. You may need to edit frontmatter in source view for nested fields.

## Retailer Notes

ProseDown produces standard EPUB 3.3, but retailers have specific expectations beyond the spec:

### Apple Books ([Asset Guide](https://help.apple.com/itc/booksassetguide/))
- **No forced body colors** in CSS — Apple inverts colors in dark/night/sepia modes. Forced black text disappears on dark backgrounds. The default stylesheet avoids this.
- **Cover minimum 1400px** on shortest edge, strictly enforced. Upscaled low-res images are rejected.
- **Interior images max 5.6 million pixels** (width × height). A 2000×2800 image is at the limit.
- **No duplicate HTML IDs** across documents — Apple rejects what Amazon silently ignores.
- **No `position: absolute/fixed`** in reflowable content — causes text overlap, rejected.
- **Series metadata** (`belongs-to-collection`) is ignored by Apple's storefront; series grouping is managed via iTunes Connect portal. Compilers SHOULD still emit it for other platforms.
- **Embedded fonts** require `<meta property="ibooks:specified-fonts">true</meta>` or WebKit ignores them. (Font embedding is a future ProseDown feature.)

### Amazon KDP ([Metadata Guidelines](https://kdp.amazon.com/help/topic/G201097560))
- **Titles/subtitles** must not contain keywords, HTML, or trademark references.
- **Series numbers** accept up to two decimal places (e.g., `1.50`). Negative numbers and complex strings are rejected.
- KDP's Enhanced Typesetting engine handles hyphenation, justification, and kerning automatically — don't overspecify these in CSS.

### General
- Compilers MUST produce unique HTML `id` attributes across all content documents.
- Compilers SHOULD disable hyphenation on headings (`hyphens: none`) — auto-hyphenated titles look bad on every platform.
- Images with text embedded as raster graphics (instead of HTML) are rejected by Apple and degrade accessibility everywhere.

## Examples

### Minimal (One File)

```markdown
---
title: "On Simplicity"
author: "Jane Smith"
---

# On Simplicity

The simplest things are often the most profound.
```

### Novel (Multi-Chapter)

**book.md:**
```yaml
---
title: "The Mountain Trail"
subtitle: "A Novel"
author: "Jeff Alldridge"
author-sort: "Alldridge, Jeff"
language: en
date: "2026"
publisher: "Tent Studios Press"
description: "A story of resilience and discovery."
isbn: "978-0-123456-78-9"
rights: "Copyright 2026 Jeff Alldridge. All rights reserved."
subject:
  - Fiction
  - Adventure
series:
  name: "The Idaho Series"
  number: 1
---
```

**00-copyright.md:**
```markdown
# Copyright

Copyright 2026 Jeff Alldridge. All rights reserved.
Published by Tent Studios Press, Idaho Falls, Idaho.
```

**01-chapter-1.md:**
```markdown
# The Trailhead

The parking lot was empty at five in the morning.
```

**02-chapter-2.md:**
```markdown
# Above the Trees

By midday the pines had given way to granite and sky.
```

**03-about-the-author.md:**
```markdown
# About the Author

Jeff Alldridge is an Art Director and writer based in Idaho Falls, Idaho.
```

Note: `00-copyright.md` is detected as `role: frontmatter` from its slug. `03-about-the-author.md` is detected as `role: backmatter`. No frontmatter needed on either file.

---

## Learn More

- **[CommonMark](https://commonmark.org/)** — the Markdown standard ProseDown builds on
- **[EPUB 3.3 Spec](https://www.w3.org/TR/epub-33/)** — the W3C standard ProseDown compiles to
- **[Fountain](https://fountain.io/)** — the screenplay format that inspired ProseDown's philosophy
- **[Standard Ebooks](https://standardebooks.org/)** — the gold standard for EPUB quality
- **[EPUBCheck](https://www.w3.org/publishing/epubcheck/)** — the official EPUB validation tool

## License

The ProseDown spec is open source under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/). Reference implementations and the default stylesheet are licensed separately.
