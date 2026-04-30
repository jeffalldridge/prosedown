# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
spec version (currently 0.6.1) and the package version are kept in lock-step
until 1.0.

## [Unreleased]

## [0.6.2] — 2026-04-30

Patch release — quickstart copy-paste now works, plus polish.

### Fixed

- **CLI: positional ``output`` argument.** The README, live site, and
  quickstart all showed
  ``prosedown build foo.md foo.epub``, but the CLI rejected that —
  the second arg required ``--output`` / ``-o``. The CLI now accepts
  positional output (with ``--output`` / ``-o`` retained as a hidden
  alias for backwards compat). Library API unchanged.
- **Spec: ``# The ProseDown Spec`` renamed to ``The ProseDown
  Specification``** and the leading ``Version 0.6.1 — Draft`` line
  dropped the ``— Draft`` suffix. The spec is published and stable;
  ``Draft`` was misleading post-release.
- **Site: spec page title is no longer duplicative**
  (``The ProseDown Specification — The ProseDown Specification``).

### Added

- **Docstrings on ~25 more internal functions** in
  ``src/prosedown/__init__.py``. Function-level coverage went from
  17% → 40%; classes were already at 100%. Public API was already
  documented; this pass covered ``build_opf``,
  ``parse_epub_metadata``, ``discover_chapters``,
  ``resolve_chapter_paths``, ``validate_project_relative_path``,
  ``write_epub_archive``, ``zipinfo_for``, and the OPF/spine/metadata
  parsing helpers — the kinds of functions a reader of the source
  would actually look up.
- **``.github/dependabot.yml``** — weekly auto-PRs for ``pip`` and
  ``github-actions`` ecosystems. Patch + minor bumps grouped per
  ecosystem; majors get individual PRs because they need closer
  review. Standard practice for security/dependency hygiene.

### Changed

- **README license badge** is now
  ``shields.io/pypi/l/prosedown`` (auto-derived from PyPI metadata)
  instead of a hardcoded ``License: MIT`` string.

## [0.6.1] — 2026-04-30

Initial public release.

### Added

- **ProseDown specification v0.6.1** — A format for writing books in
  Markdown and compiling them to EPUB. CommonMark + YAML frontmatter, two
  required fields, no custom syntax. See [`spec/prosedown.md`](spec/prosedown.md).
- **Reference compiler / deconstructor** (`prosedown` Python package).
  - `prosedown build <project> <out.epub>` — Markdown → EPUB 3.3 (passes
    [EPUBCheck](https://www.w3.org/publishing/epubcheck/) without errors)
  - `prosedown deconstruct <book.epub> <project-dir>` — EPUB → Markdown
    (best-effort, with documented normalization)
- **Default stylesheet** (`prosedown-default.css`) bundled inside the package.
- **XHTML mapping reference** (`spec/xhtml-mapping.md`) for implementers
  writing alternate compilers.
- **Four example projects** under `spec/examples/`:
  - `single-file/` — a one-file essay
  - `multi-chapter/` — a folder of numbered chapters
  - `multi-part/` — a multi-part book with parts and front/back matter
  - `with-features/` — exercises images, captions, glossary
- **Synthetic test suite** (36 tests) covering unit-level algorithms,
  regression scenarios (special characters, repeated builds, large file
  counts), and full round-trips on the example projects.
- **Optional corpus mode** — set `PROSEDOWN_CORPUS=<dir>` to run additional
  tests against Standard Ebooks, Project Gutenberg, Google Docs exports,
  and commercial samples. The corpus is not redistributed.

### Notes

- Python 3.10+.
- This is a pre-1.0 release. The spec is stable enough to use; minor
  refinements are likely before 1.0.
- Build path uses only MIT- and BSD-licensed dependencies; the
  `deconstruct` path additionally uses `html2text` (GPL-3.0+) and
  `EbookLib` (AGPL-3.0+). See [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
