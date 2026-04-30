# Why ProseDown

Most ebook tools fall into one of three categories:

1. **Closed editors** — Vellum, Scrivener. Beautiful output. Your
   manuscript lives inside the app's database. To open it in another
   tool you have to export, and the export usually loses something.
2. **Power tools** — Pandoc, LaTeX. Will produce any output format you
   can imagine, with citation engines, custom syntax, plugins. The
   learning curve is the price.
3. **Raw EPUB editors** — Sigil, Calibre. You're hand-editing XHTML
   inside a zip file. Useful for fixing existing books, painful for
   writing new ones.

ProseDown is a different point in the design space:

> Plain Markdown source files an author can open in any editor —
> [Obsidian](https://obsidian.md), VS Code, iA Writer, TextEdit,
> Notepad — that compile to a professional EPUB by convention, with
> no configuration.

That's the whole pitch.

## Five design principles

These are stated in the spec but worth restating in plain language:

1. **One file is enough.** A single `.md` with `title:` and `author:`
   frontmatter is a valid project. The barrier to entry is zero.
2. **Convention over configuration.** Cover image auto-detected by
   filename. CSS auto-detected. Chapter order from filenames. Authors
   shouldn't configure what can be inferred.
3. **Standard everything.** [CommonMark](https://commonmark.org/)
   Markdown. Standard YAML frontmatter. No custom syntax. Lock-in is the
   enemy of adoption.
4. **Two directions.** Compile any project to EPUB. Deconstruct most
   reflowable EPUBs back to Markdown (best-effort). Build is the primary
   use case — stable and deterministic.
5. **Non-destructive.** Opening a ProseDown project in Obsidian, Hugo,
   or Jekyll doesn't break anything. A format that fights your other
   tools isn't a format worth adopting.

## What it's *not* for

ProseDown is for **reflowable prose**: fiction, narrative non-fiction,
essays, memoirs, how-to books, devotionals — anything that's primarily
text and reads well on any screen size.

It's **not** for:

- Fixed-layout books / picture books / comics (Markdown is reflowable
  by nature; you need pixel positioning)
- Poetry with line-level semantics (`epub:type="z3998:verse"`, hanging
  indents — not expressible in CommonMark)
- Drama (cast lists need semantic table markup)
- Academic citations (need a citation engine)
- Media overlays / read-aloud (needs SMIL)
- DRM (your distributor handles that)
- PDF output (different layout model)

These are scope boundaries, not future features. If your book needs one
of them, use a different tool.

## How it compares

### vs. Vellum

Vellum produces beautiful EPUBs with one click. The catch:

- macOS only
- $250 one-time
- Closed file format (`.vellum`) — your manuscript only opens in Vellum
- Limited customization (you get Vellum's templates, not yours)

ProseDown is platform-agnostic plain text. You won't get Vellum's
typography polish out of the box, but your source files outlive the
tool.

### vs. Pandoc

Pandoc is the industrial-strength workhorse. It can:

- Convert dozens of formats (LaTeX, DOCX, HTML, EPUB, PDF, …)
- Run citation engines via `citeproc`
- Apply custom Lua filters
- Use template engines

Power costs configuration. A Pandoc EPUB build typically wants a
metadata file, a CSS file, a `--toc`, sometimes a custom template. For
the 80% case of "compile this Markdown folder into an EPUB," that's a
lot of moving parts.

ProseDown is opinionated Pandoc without the dial-twiddling. If you need
the dials, use Pandoc.

### vs. raw EPUB editors (Sigil, Calibre)

Sigil and Calibre are great when you have an existing EPUB to fix.
They're fundamentally about XHTML editing inside a zip file. Writing a
book from scratch in them is like writing a website by hand-editing
its `dist/` directory.

ProseDown deconstruction goes the other way: an existing EPUB out, into
a Markdown project you can edit in your favorite tool, then rebuild.

## Who this is for

- **Authors** who want plain-text source they can edit anywhere, version
  with git, and back up trivially.
- **Indie publishers** who produce reflowable ebooks and don't need
  fixed-layout features.
- **Developers** building tools on top of an open format — VS Code
  extensions, Obsidian plugins, conversion pipelines.
- **Archivists** who want a path from old EPUBs back into editable
  Markdown.

## Who this is *not* for

- Authors who want a polished GUI editor that handles everything for
  them. Vellum is much better at this.
- Anyone publishing a print book primarily, with EPUB as an
  afterthought. PDF / InDesign / LaTeX is a more direct path.
- Authors of fixed-layout books (children's books, comics, technical
  books with pixel-precise layout).

## What's stable, what's not

- **The build path** (Markdown → EPUB) is stable. Same input → same
  output, deterministic, EPUBCheck-clean. Subsequent versions of the
  spec should be backwards-compatible.
- **The deconstruct path** (EPUB → Markdown) is best-effort and will
  improve. Edge cases produce diagnostics in the output; some EPUB
  artifacts deliberately don't survive the round-trip (because they'd
  pollute the Markdown source).
- **The spec** is at v0.6.1. Pre-1.0 we will refine. After 1.0 we won't
  break it lightly.
