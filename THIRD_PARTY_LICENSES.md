# Third-Party Licenses

ProseDown is built on top of the following Python libraries. Each is used
under the terms of its own license. See each project's repository for the
full license text.

## Runtime dependencies

| Package | License | Use |
|---|---|---|
| [`Markdown`](https://github.com/Python-Markdown/markdown) | BSD-3-Clause | CommonMark parsing |
| [`PyYAML`](https://github.com/yaml/pyyaml) | MIT | YAML frontmatter parsing |
| [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/) | MIT | HTML parsing during deconstruction |
| [`lxml`](https://lxml.de/) | BSD-3-Clause | XHTML / OPF / NCX generation |
| [`html2text`](https://github.com/Alir3z4/html2text) | GPL-3.0-or-later | XHTML → Markdown conversion during deconstruction |
| [`EbookLib`](https://github.com/aerkalov/ebooklib) | AGPL-3.0-or-later | EPUB file parsing during deconstruction |

## License compatibility note

Two of the runtime dependencies (`html2text` GPL-3.0+ and `EbookLib` AGPL-3.0+)
are copyleft licenses. ProseDown itself is MIT-licensed, but **distributing
binary builds that include these dependencies is subject to the copyleft
terms**. In practice this means:

- Installing ProseDown via `pip install prosedown` is fine — the user pulls
  each dependency under its own license, no aggregation.
- Bundling ProseDown into a closed-source application would require that
  application to comply with GPL/AGPL terms.
- The ProseDown source code itself remains MIT.

If you need a fully MIT-licensed deconstruction path, the GPL/AGPL deps are
only used by the `deconstruct` command. The `build` command path (the primary
ProseDown use case) only uses MIT- and BSD-licensed deps.

## Specification

The ProseDown specification document (`spec/prosedown.md`) is also released
under the MIT License. You're free to implement compatible compilers and
deconstructors in any language, with attribution.

## Default stylesheet

`src/prosedown/data/prosedown-default.css` is original work, MIT-licensed
along with the rest of the project.

## Reference standards

ProseDown conforms to and references these public specifications, which are
freely available but not redistributed in this repo:

- [EPUB 3.3](https://www.w3.org/TR/epub-33/) — W3C Recommendation
- [CommonMark](https://commonmark.org/) — open spec
- [XHTML 1.1](https://www.w3.org/TR/xhtml11/) — W3C Recommendation
- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) — IETF Best Practice
- [RFC 4122](https://www.rfc-editor.org/rfc/rfc4122) — UUID generation

## Test fixtures

The synthetic example projects under `spec/examples/` are original works
written for this repository, MIT-licensed.

ProseDown's development used a corpus of real EPUBs from
[Standard Ebooks](https://standardebooks.org/), [Project Gutenberg](https://www.gutenberg.org/),
Google Docs exports, and commercial samples for testing. **None of those
files are redistributed via this repository.** Maintainers point at a local
corpus by setting the `PROSEDOWN_CORPUS` environment variable; see
`tests/test_suite.py` for the expected layout.
