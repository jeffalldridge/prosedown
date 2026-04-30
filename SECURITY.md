# Security Policy

## Supported versions

Only the latest tagged release is actively supported.

## Reporting a vulnerability

If you find a security issue — for example, a path-traversal in
`deconstruct` (writing files outside the target directory), a zip-bomb in
EPUB extraction, a way to inject arbitrary content into the generated EPUB
that bypasses sanitization, or anything that could compromise the user's
machine — please **don't open a public GitHub issue.**

Instead, email **jeff.alldridge@gmail.com** with:

- A description of the issue
- A minimal reproducer (a small `.epub` or `.md` file that triggers it)
- Your suggested severity rating

You should expect a response within a few days. Once the issue is fixed
and released, you'll be credited in the changelog (unless you'd rather
stay anonymous).

## Threat model

ProseDown is a local CLI tool. It:

- Reads `.md` files and EPUB containers from disk
- Writes `.epub` and `.md` files to disk
- Does not phone home, log telemetry, or call any external network service
- Does not execute arbitrary code from input files (Markdown rendering
  uses a safe subset; HTML escaping is mandatory)

Practical attack surface is therefore:

- **EPUB extraction (`deconstruct`)** — zip parsing of attacker-controlled
  archives. We use Python's `zipfile`, which is hardened against zip-bomb
  expansion and path traversal in modern stdlib, but care is taken
  explicitly when writing extracted files.
- **HTML parsing** — `beautifulsoup4` + `lxml` parsing untrusted XHTML.
  These libraries are battle-tested but XML/HTML parsers occasionally
  ship XXE or billion-laughs CVEs; we keep deps current.
- **Markdown → XHTML rendering (`build`)** — input is the user's own
  Markdown so the threat model is "did we sanitize properly enough that
  e-readers don't see broken XHTML." Not a privilege boundary.

Issues outside this scope (e.g. CommonMark spec ambiguities, e-reader
rendering quirks) are bugs but not security issues.
