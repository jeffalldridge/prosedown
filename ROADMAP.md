# Roadmap

Where ProseDown is going. This document is **a guide, not a contract** —
priorities can change, especially based on what you tell us in
[issues](https://github.com/jeffalldridge/prosedown/issues) and
[discussions](https://github.com/jeffalldridge/prosedown/discussions).

The current spec is at [`spec/prosedown.md`](spec/prosedown.md). The
release in your hand is **v0.6.1**.

---

## ✅ Shipped — v0.6.1 (2026-04-30)

Initial public release.

- **Specification v0.6.1** — CommonMark + YAML frontmatter, two required
  fields, no custom syntax. EPUB 3.3 conformance.
- **Reference compiler / deconstructor** in Python (`prosedown` on PyPI).
- **36/36 synthetic tests** plus opt-in real-world corpus mode.
- **CI matrix** Python 3.10–3.13 × Ubuntu+macOS.
- **Default stylesheet** bundled in the wheel.
- **XHTML mapping reference** for alternate-language implementations.
- **Four example projects**: single-file, multi-chapter, multi-part,
  with-features.

---

## 🛠 Working on — v0.7 (target: Q3 2026)

Status: design phase. PRs welcome with prior issue discussion.

### Spec

- **Font embedding.** People keep asking. Frontmatter syntax for
  `fonts:` declaring `.woff2` files; CLI bundles them into the EPUB and
  references them in the default CSS.
- **Pandoc-style metadata aliases.** Accept `creator:` as a synonym for
  `author:`, `lang:` for `language:`, etc. Lowers the friction for users
  migrating from other tools without changing the canonical form.
- **Per-chapter CSS classes.** `class:` frontmatter field that maps to
  `<section class="...">` so the default stylesheet's named layouts
  (`prose-large`, `prose-letter`) become opt-in.

### CLI

- **`prosedown new <name>`** scaffold command that creates a starter
  project with frontmatter and a sample chapter. Lowers the barrier from
  "read the docs" to "type two commands."
- **`prosedown check <project>`** to validate without building. Outputs
  the same diagnostics build produces but skips packaging.
- **Better progress output** during long deconstructions.
- **Cancellation handling** (ctrl-C cleans up partial output).

### Quality

- **pytest migration** — the bespoke test runner has served us well, but
  pytest gives us better fixtures, parallelization, and report formats.
  Tests stay logically the same.
- **Coverage tracking** in CI with codecov.
- **Mutation testing** pass to find blind spots.

---

## 📐 Toward v1.0 — spec lock (target: end of 2026)

v1.0 is the spec-lock release. Once we're at 1.0, breaking changes need
a major version bump. Acceptance criteria:

- **Stable spec** — no semantic changes for two minor versions running.
  Wording polish is fine; behavior changes are not.
- **At least one independent compiler** in another language (Rust or Go
  candidate — see "Help wanted" below).
- **Round-trip stability** — building the same project at v1.0.0 and
  v1.0.1 produces byte-identical EPUBs (modulo timestamps).
- **EPUBCheck-clean across 100+ real-world test corpus** without any
  warnings. Today we're EPUBCheck-error-free; the warning bar comes next.

After v1.0 the project moves to a slower cadence — patch releases for
bug fixes, minor for additive features, major releases planned and
discussed publicly.

---

## 🔭 Maybe / later

Not actively scheduled. We'll prioritize based on user feedback.

- **VS Code extension** — preview-as-you-type for ProseDown projects,
  sidebar with chapter navigation, "Build EPUB" command palette entry.
- **Obsidian plugin** — same idea, since Obsidian is one of the most
  popular Markdown editors among writers.
- **Web playground** — drop a ProseDown project zip into a browser, see
  a preview. Useful for newcomers who want to try before installing.
- **Pandoc filter** — call ProseDown's compiler from Pandoc's pipeline.
- **Output to alternative formats** — HTML site, PDF (via WeasyPrint).
  Note: this is a sharp deviation from the EPUB-focused mission;
  probably stays in this list.
- **Docker image** for users who want a no-Python install path.
- **Homebrew formula** — `brew install prosedown` one day.

---

## 🚫 Out of scope (not happening)

These are spec boundaries, not future features. Per
[the spec](spec/prosedown.md#what-prosedown-is-for-and-not-for):

- **Fixed-layout EPUBs** (picture books, comics, technical books with
  pixel-precise layout). Use Sigil or Vellum.
- **Poetry with line-level semantics** (`epub:type="z3998:verse"`,
  hanging indents). Use Pandoc.
- **Drama formatting** (cast lists, dialogue attribution as semantic
  tables). Use Pandoc.
- **Academic citations** (citation engines, bibliography generation).
  Use Pandoc with citeproc, or LaTeX.
- **Media overlays** (audio-synced narration via SMIL). Use DAISY tools.
- **DRM / encryption.** Your distributor handles DRM.
- **PDF output as primary format.** Different layout model. ProseDown
  produces EPUB.

---

## 🤝 Help wanted

We're a one-person project today. Real contributions that would
meaningfully advance the project:

- **An independent compiler in Rust or Go.** This is the #1 thing
  needed for v1.0. Implementing the spec from scratch in another
  language is the surest way to find ambiguities. Reach out via an
  issue if interested — we'll prioritize spec clarification PRs to make
  your life easier.
- **Real-world corpus testing.** If you have a collection of EPUBs
  (Standard Ebooks, your own published work, public-domain) and can
  point ProseDown at them with `PROSEDOWN_CORPUS=...`, the bug reports
  are gold.
- **Translations of the spec / docs.** Once we hit v1.0 the spec is
  worth translating; before then it's a moving target.

---

## How decisions get made

Spec changes go through the **Spec question / proposal** issue template.
Discussion happens in the issue; the PR implements the agreed change.
Pre-1.0 we will refine the spec; after 1.0 we won't lightly.

Code changes follow [`CONTRIBUTING.md`](CONTRIBUTING.md). Tests required,
CI must pass, screenshots for UX changes.

Roadmap revisions land here in PRs with the reasoning in the commit
message. Anything in this file is reversible until shipped.
