# Contributing

Thanks for the interest. ProseDown is small enough that any contribution
moves it forward; that also means the bar for code quality is high.

## Two kinds of contributions

This repo holds **two separate things** in the same tree:

1. **The ProseDown specification** (`spec/prosedown.md`) — the source of
   truth for what a conforming compiler must do.
2. **A reference implementation** (`src/prosedown/`) — one Python compiler
   and deconstructor.

Spec changes and code changes have different review bars.

### Spec changes

The spec is a contract between independent compilers. Even one-word changes
can have outsized impact. PRs that touch `spec/prosedown.md`:

- Open an issue first using the **Spec question** template, even if you
  already know the answer. Discussion lives in the issue; the PR
  implements the agreed change.
- Cite specific sections of the [EPUB 3.3](https://www.w3.org/TR/epub-33/)
  or [CommonMark](https://commonmark.org/) specs when proposing semantic
  changes.
- Note any breaking changes loudly. Pre-1.0 we will break things; after 1.0
  we won't lightly.

### Code changes

PRs that touch `src/`, `tests/`, or tooling:

- Open them small and focused. One bug fix, one feature, one PR.
- Tests required for new functionality — the suite lives at
  `tests/test_suite.py` and runs in CI on every push.
- Run the full suite locally before pushing: `python tests/test_suite.py`.
  All 36 synthetic tests must stay green.
- If you have a real-world corpus locally, also run with
  `PROSEDOWN_CORPUS=/path/to/corpus python tests/test_suite.py` to catch
  regressions outside the synthetic set.

## Getting set up

```sh
git clone https://github.com/jeffalldridge/prosedown
cd prosedown
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

prosedown --help
python tests/test_suite.py
```

You need **Python 3.10+**. Older versions won't install via pip.

## Keep dependencies minimal

The runtime dependency list is intentionally short (six packages). Adding
a new one needs a justification stronger than "it's convenient." If a
dependency is only used in one helper function, copy the helper instead.

## Style

- **Type hints required** on new functions.
- Match the existing module's style — single-file, function-oriented,
  dataclasses for structured data, no class hierarchies for the sake of
  it.
- No black / isort / ruff config (yet). Keep diffs visually clean, two
  blank lines between top-level definitions.
- Don't reflow unrelated code in a PR. Touch only what your change
  requires.

## Filing issues

Three issue templates:

1. **Bug** — something doesn't work the way the spec says it should
2. **Feature** — a use case the tool should support
3. **Spec question** — a question about the spec itself, or a proposed
   spec change

Use the right one; it routes the conversation correctly.

## Security

For security-sensitive issues, see [`SECURITY.md`](SECURITY.md). Don't open
public issues for those.
