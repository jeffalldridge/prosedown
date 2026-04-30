#!/usr/bin/env python3
"""ProseDown — Markdown ↔ EPUB compiler and deconstructor.

ProseDown is a format for writing books in Markdown and compiling them
to EPUB 3.3. This module is the reference implementation, conforming to
the spec at ``spec/prosedown.md`` (in this repository).

Two directions, with different stability promises:

- :func:`build` (Markdown → EPUB) is the **primary use case**. Stable,
  reproducible, deterministic. Same source, same output. Output passes
  EPUBCheck without errors.
- :func:`deconstruct` (EPUB → Markdown) is **best-effort** with documented
  normalization. The goal is readable Markdown an author would want to
  edit, not a lossless archive of the original EPUB.

Library use::

    from prosedown import build, deconstruct
    build("path/to/project", "out.epub")
    deconstruct("book.epub", "recovered/")

CLI use::

    prosedown build path/to/project out.epub
    prosedown deconstruct book.epub recovered/

Public API:

- Functions: :func:`build`, :func:`deconstruct`, :func:`parse_frontmatter`,
  :func:`slugify`, :func:`title_resolution`, :func:`canonical_uuid_input`,
  :func:`deterministic_uuid`, :func:`smartypants_segment`
- Classes: :class:`MarkdownRenderer`, :class:`Diagnostic`,
  :class:`DiagnosticBag`, :class:`BuildDocument`,
  :class:`ParsedEpubDocument`

The full API is exported via ``__all__`` below.
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import sys
import unicodedata
import uuid
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlparse

import html2text
import markdown
import yaml
from bs4 import BeautifulSoup, NavigableString, Tag
from lxml import etree


# ----------------------------------------------------------------------------
# Package metadata
# ----------------------------------------------------------------------------

# Resolve the version from installed package metadata so it stays in sync with
# pyproject.toml. Fall back to a sentinel for in-place runs against a checkout
# without an installed dist (e.g. `python tests/test_suite.py` from a fresh
# clone before `pip install -e .`).
try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("prosedown")
except PackageNotFoundError:  # pragma: no cover — only hit in dev without an install
    __version__ = "0.0.0+local"

__all__ = [
    "__version__",
    # primary entry points
    "build",
    "deconstruct",
    "main",
    # parsing helpers
    "parse_frontmatter",
    "split_frontmatter",
    # diagnostics
    "Diagnostic",
    "DiagnosticBag",
    # data models
    "BuildDocument",
    "ParsedMarkdownFile",
    "ParsedEpubDocument",
    "ContentAsset",
    "HeadingEntry",
    "TocEntry",
    # rendering
    "MarkdownRenderer",
    # well-tested utilities (used by tests + downstream tools)
    "slugify",
    "deslugify",
    "title_resolution",
    "canonical_uuid_input",
    "deterministic_uuid",
    "smartypants_segment",
    "normalize_author_list",
]


PROSEDOWN_UUID_NAMESPACE = uuid.UUID("a0b1c2d3-e4f5-6789-abcd-ef0123456789")

MARKDOWN_EXTENSIONS = [
    "markdown.extensions.footnotes",
    "markdown.extensions.tables",
    "markdown.extensions.def_list",
    "markdown.extensions.fenced_code",
]

AUTO_DISCOVERY_RE = re.compile(r"^(\d+)-.+\.md$")
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)
FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^([^\]]+)\]:")
REMOTE_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
URLISH_RE = re.compile(r"(?:https?://|mailto:|www\.)\S+", re.IGNORECASE)
EVENT_ATTR_RE = re.compile(r"^on", re.IGNORECASE)

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XLINK_NS = "http://www.w3.org/1999/xlink"

XML_NAMESPACES = {
    "dc": DC_NS,
    "opf": OPF_NS,
    "epub": EPUB_NS,
    "xml": XML_NS,
    "ncx": NCX_NS,
    "container": CONTAINER_NS,
}

FRONTMATTER_SLUGS = {
    "copyright",
    "dedication",
    "acknowledgments",
    "acknowledgements",
    "foreword",
    "preface",
    "epigraph",
    "prologue",
    "titlepage",
    "halftitlepage",
    "table-of-contents",
    "toc",
}

BACKMATTER_SLUGS = {
    "appendix",
    "bibliography",
    "glossary",
    "about-the-author",
    "colophon",
    "afterword",
    "epilogue",
    "endnotes",
}

PART_RE = re.compile(r"^part-\d+$")

SPECIFIC_EPUB_TYPES = {
    "copyright": "imprint",
    "dedication": "dedication",
    "foreword": "foreword",
    "preface": "preface",
    "prologue": "prologue",
    "epilogue": "epilogue",
    "appendix": "appendix",
    "bibliography": "bibliography",
    "glossary": "glossary",
    "colophon": "colophon",
    "afterword": "afterword",
    "about-the-author": "contributors",
}

EPUB_TYPE_TO_ROLE = {
    "frontmatter": "frontmatter",
    "bodymatter": "chapter",
    "backmatter": "backmatter",
    "chapter": "chapter",
    "part": "part",
    "imprint": "frontmatter",
    "copyright-page": "frontmatter",
    "dedication": "frontmatter",
    "foreword": "frontmatter",
    "preface": "frontmatter",
    "prologue": "frontmatter",
    "introduction": "frontmatter",
    "epigraph": "frontmatter",
    "titlepage": "frontmatter",
    "halftitlepage": "frontmatter",
    "epilogue": "backmatter",
    "appendix": "backmatter",
    "bibliography": "backmatter",
    "glossary": "backmatter",
    "contributors": "backmatter",
    "colophon": "backmatter",
    "afterword": "backmatter",
    "endnotes": "backmatter",
}

EPUB_TYPE_TO_SLUG = {
    "imprint": "copyright",
    "copyright-page": "copyright",
    "dedication": "dedication",
    "foreword": "foreword",
    "preface": "preface",
    "prologue": "prologue",
    "epigraph": "epigraph",
    "appendix": "appendix",
    "bibliography": "bibliography",
    "glossary": "glossary",
    "contributors": "about-the-author",
    "colophon": "colophon",
    "afterword": "afterword",
    "epilogue": "epilogue",
    "titlepage": "titlepage",
    "halftitlepage": "titlepage",
    "cover": "cover",
    "toc": "table-of-contents",
    "endnotes": "endnotes",
}

GUIDE_TYPE_TO_ROLE = {
    "cover": "frontmatter",
    "toc": "frontmatter",
    "title-page": "frontmatter",
    "copyright-page": "frontmatter",
    "dedication": "frontmatter",
    "foreword": "frontmatter",
    "preface": "frontmatter",
    "prologue": "frontmatter",
    "appendix": "backmatter",
    "bibliography": "backmatter",
    "glossary": "backmatter",
    "colophon": "backmatter",
    "afterword": "backmatter",
    "notes": "backmatter",
}

GUIDE_TYPE_TO_SLUG = {
    "cover": "cover",
    "toc": "table-of-contents",
    "title-page": "titlepage",
    "copyright-page": "copyright",
    "dedication": "dedication",
    "foreword": "foreword",
    "preface": "preface",
    "prologue": "prologue",
    "appendix": "appendix",
    "bibliography": "bibliography",
    "glossary": "glossary",
    "colophon": "colophon",
    "afterword": "afterword",
    "notes": "endnotes",
}

VOID_ELEMENTS = {"img", "br", "hr", "meta", "link"}


@dataclass
class Diagnostic:
    """A build / deconstruct issue.

    Diagnostics are accumulated into a :class:`DiagnosticBag` during
    parsing, validation, rendering, and packaging. They are emitted at the
    end of the run so the user sees a coherent summary instead of being
    bombarded mid-build.

    :param level: ``"error"`` or ``"warning"``. Errors fail the build;
        warnings do not.
    :param message: Human-readable description.
    :param path: Optional source-file path the diagnostic refers to.
    """

    level: str
    message: str
    path: str | None = None


@dataclass
class DiagnosticBag:
    """Accumulates diagnostics during a build / deconstruct run.

    Use :meth:`error` or :meth:`warn` to add issues; :meth:`emit` at the
    end of the run prints them all to stdout/stderr in a stable order.
    :attr:`has_errors` is what the public functions check to decide their
    boolean return value.
    """

    items: list[Diagnostic] = field(default_factory=list)

    def error(self, message: str, path: str | Path | None = None) -> None:
        """Record an error. The build will fail if any are present."""
        self.items.append(Diagnostic("error", message, None if path is None else str(path)))

    def warn(self, message: str, path: str | Path | None = None) -> None:
        """Record a warning. Doesn't fail the build."""
        self.items.append(Diagnostic("warning", message, None if path is None else str(path)))

    @property
    def has_errors(self) -> bool:
        """True if any error-level diagnostic has been recorded."""
        return any(item.level == "error" for item in self.items)

    def emit(self) -> None:
        """Print all diagnostics. Errors → stderr, warnings → stdout."""
        for item in self.items:
            prefix = "Error" if item.level == "error" else "Warning"
            if item.path:
                print(f"{prefix}: {item.path}: {item.message}", file=sys.stderr if item.level == "error" else sys.stdout)
            else:
                print(f"{prefix}: {item.message}", file=sys.stderr if item.level == "error" else sys.stdout)


@dataclass
class ParsedMarkdownFile:
    """A Markdown file that has been read and split into frontmatter + body.

    The body is the raw Markdown text below the frontmatter; rendering to
    XHTML happens later in the pipeline via :class:`MarkdownRenderer`.

    :param path: Filesystem path to the source file.
    :param source_ref: Project-relative reference used in diagnostics.
    :param meta: Decoded YAML frontmatter dict. May be empty.
    :param body: Raw Markdown text below the frontmatter.
    """

    path: Path
    source_ref: str
    meta: dict
    body: str


@dataclass
class HeadingEntry:
    """One heading discovered while rendering Markdown.

    Used to build chapter-internal navigation and the auto-generated
    table of contents.
    """

    level: int
    text: str
    anchor: str
    children: list["HeadingEntry"] = field(default_factory=list)


@dataclass
class TocEntry:
    """One entry in the EPUB's navigation document.

    EPUB 3 requires a ``nav`` element; this models a single hierarchical
    item before serialization to XHTML.
    """

    title: str
    href: str
    children: list["TocEntry"] = field(default_factory=list)


@dataclass
class BuildDocument:
    """One source file resolved into all the data the pipeline needs.

    Created during ``build``'s resolution phase: each Markdown file (or
    the single-file project) becomes one ``BuildDocument``. Carries the
    parsed frontmatter, raw Markdown, derived title, EPUB role
    (``cover`` / ``titlepage`` / ``chapter`` / etc.), navigation flags,
    and — after rendering — the generated XHTML body.

    Most fields are populated by the resolution pass; :attr:`html_body`
    and :attr:`heading_entries` get filled in by :class:`MarkdownRenderer`.
    """

    source_ref: str
    source_path: Path | None
    source_slug: str
    output_stem: str
    file_name: str
    meta: dict
    body_markdown: str
    title: str
    role: str
    include_in_toc: bool
    toc_override: bool | None
    authors: list[str]
    language: str
    body_epub_type: str
    section_epub_type: str
    section_aria_role: str | None
    html_body: str = ""
    heading_entries: list[HeadingEntry] = field(default_factory=list)
    anchor_ids: set[str] = field(default_factory=set)
    links: list[str] = field(default_factory=list)
    used_assets: set[str] = field(default_factory=set)
    declared_title: str | None = None
    first_heading: str | None = None


@dataclass
class ContentAsset:
    """A binary asset (image, font, etc.) referenced by the project.

    Resolved relative to the project root and packaged into the EPUB
    under the same href used in the Markdown source.
    """

    href: str
    data: bytes
    media_type: str


@dataclass
class ParsedEpubDocument:
    """One spine document extracted from an EPUB during deconstruction.

    Holds enough state for the deconstructor to convert the XHTML back
    to clean Markdown: the parsed BeautifulSoup tree, the document's
    role (cover / titlepage / chapter / etc.), and the slug to use when
    naming the output Markdown file.
    """

    spine_index: int
    href: str
    title: str | None
    role: str
    toc_override: bool | None
    source_slug: str
    soup: BeautifulSoup
    body_root: Tag | BeautifulSoup


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def trimmed_string(value: object) -> str | None:
    if value is None:
        return None
    text = nfc(str(value)).strip()
    return text or None


def normalize_path_string(value: str) -> str:
    return value.replace("\\", "/")


def slugify(text: str | None) -> str:
    """Lowercase, hyphen-separated, ASCII-alphanumeric form of ``text``.

    Used for filenames inside the EPUB (chapter HTMLs, internal anchors,
    asset hrefs). Preserves Unicode letters' alphanumeric status via
    :func:`str.isalnum` so non-ASCII titles get sensible slugs. Returns
    ``"section"`` if the input collapses to nothing.

        >>> slugify("Chapter 1: The Beginning")
        'chapter-1-the-beginning'
        >>> slugify(None)
        'section'
    """
    value = nfc(text or "").lower()
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = "".join(ch for ch in value if ch.isalnum() or ch == "-")
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("-")
    return value or "section"


def deslugify(slug: str) -> str:
    """Inverse of :func:`slugify` for display.

    Used as a fallback chapter title when no frontmatter title is set
    and the chapter has no ``# heading``. ``"about-the-author"`` →
    ``"About The Author"``. Not perfect (lowercases like "the" stay
    capitalized) but fine for synthesized titles.
    """
    words = re.sub(r"[-_]+", " ", slug).strip()
    if not words:
        return "Section"
    return " ".join(part[:1].upper() + part[1:] for part in words.split())


def detect_role_from_slug(slug: str) -> str:
    """Classify a chapter file by its slug.

    Returns one of ``"frontmatter"``, ``"part"``, ``"backmatter"``, or
    ``"chapter"``. Used to set the EPUB ``epub:type`` attribute and the
    navigation hierarchy. Recognized slugs (``copyright``, ``dedication``,
    ``part-1``, ``afterword``, etc.) are listed in
    ``FRONTMATTER_SLUGS`` / ``BACKMATTER_SLUGS`` / ``PART_RE`` above.
    """
    key = slug.lower().replace("_", "-")
    if key in FRONTMATTER_SLUGS:
        return "frontmatter"
    if key in BACKMATTER_SLUGS:
        return "backmatter"
    if PART_RE.fullmatch(key):
        return "part"
    return "chapter"


def normalize_author_list(value: object) -> list[str]:
    """Coerce frontmatter ``author`` into a list of cleaned strings.

    YAML allows ``author: "Jane Smith"`` (string) or
    ``author: ["Jane Smith", "John Doe"]`` (list). Either form is
    accepted; the result is always a list (possibly empty) of trimmed,
    NFC-normalized strings.
    """
    if isinstance(value, list):
        items = [trimmed_string(item) for item in value]
        return [item for item in items if item]
    single = trimmed_string(value)
    return [single] if single else []


def canonical_uuid_input(title: str, authors: list[str], language: str) -> str:
    """Build the canonical input string for the deterministic EPUB UUID.

    Joins title + authors + language with ``|`` after NFC normalization
    and trimming. Same input produces the same UUID across machines and
    runs, so building the same project twice produces an identical EPUB
    (modulo timestamps).

    Used by :func:`deterministic_uuid`.
    """
    clean_title = nfc(title.strip())
    clean_authors = [nfc(author.strip()) for author in authors]
    clean_language = nfc(language.strip())
    return f"{clean_title}|{'|'.join(clean_authors)}|{clean_language}"


def deterministic_uuid(title: str, authors: list[str], language: str) -> str:
    """Generate the EPUB ``dc:identifier`` deterministically from metadata.

    EPUB requires a unique identifier; ProseDown derives one with UUID v5
    over a fixed namespace (``PROSEDOWN_UUID_NAMESPACE``) and the
    canonical input from :func:`canonical_uuid_input`. Two builds of the
    same project produce the same identifier, which makes the output
    reproducible — diff-friendly under git.
    """
    return str(uuid.uuid5(PROSEDOWN_UUID_NAMESPACE, canonical_uuid_input(title, authors, language)))


def title_resolution(meta_title: str | None, first_heading: str | None, fallback_slug: str) -> str:
    """Pick a chapter title using the documented precedence.

    Per the spec:

    1. Frontmatter ``title`` if set
    2. Otherwise the first ``#`` heading in the body
    3. Otherwise a deslugified version of the filename

    Same logic applies during deconstruction so round-trips preserve the
    title source.
    """
    if meta_title is not None:
        return meta_title
    if first_heading is not None:
        return first_heading
    return deslugify(fallback_slug)


def is_remote_url(value: str | None) -> bool:
    return bool(value and REMOTE_SCHEME_RE.match(value.strip()))


def is_absolute_reference(value: str) -> bool:
    return value.startswith("/") or WINDOWS_ABS_RE.match(value) is not None


def role_to_types(role: str, slug: str) -> tuple[str, str, str | None]:
    if role == "part":
        return "bodymatter", "part", "doc-part"
    if role == "frontmatter":
        return "frontmatter", SPECIFIC_EPUB_TYPES.get(slug, "frontmatter"), None
    if role == "backmatter":
        return "backmatter", SPECIFIC_EPUB_TYPES.get(slug, "backmatter"), None
    return "bodymatter", "chapter", "doc-chapter"


def media_type_for_path(path: str | Path) -> str | None:
    suffix = Path(path).suffix.lower()
    return {
        ".css": "text/css",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".xhtml": "application/xhtml+xml",
        ".html": "application/xhtml+xml",
        ".ncx": "application/x-dtbncx+xml",
    }.get(suffix)


def read_utf8_text(path: Path, diagnostics: DiagnosticBag) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        diagnostics.error(f"Unable to read file: {exc}", path)
        return None
    if b"\x00" in data:
        diagnostics.error("NUL bytes in source files MUST produce an error", path)
        return None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        diagnostics.error("Invalid UTF-8 in source files", path)
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str, source: Path | str, diagnostics: DiagnosticBag) -> tuple[dict, str] | tuple[None, None]:
    """Parse YAML frontmatter at the top of a Markdown file.

    Frontmatter is a YAML block delimited by ``---`` lines at the very
    start of the file. Anything before the opening ``---`` is treated
    as no-frontmatter (returns ``({}, text)``). Malformed YAML or a
    non-mapping frontmatter is an error.

    :returns: ``(meta_dict, body_str)`` on success;
        ``(None, None)`` on parse failure with diagnostics recorded.
    """
    if not text.startswith("---\n"):
        return {}, text
    match = FRONTMATTER_RE.match(text)
    if not match:
        diagnostics.error("Malformed YAML frontmatter", source)
        return None, None
    yaml_block = match.group(1)
    body = text[match.end():]
    try:
        parsed = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        diagnostics.error(f"Malformed YAML frontmatter: {exc}", source)
        return None, None
    if not isinstance(parsed, dict):
        diagnostics.error("Frontmatter must be a YAML mapping", source)
        return None, None
    return parsed, body


def load_markdown_file(path: Path, project_root: Path, diagnostics: DiagnosticBag) -> ParsedMarkdownFile | None:
    text = read_utf8_text(path, diagnostics)
    if text is None:
        return None
    meta, body = split_frontmatter(text, path, diagnostics)
    if meta is None:
        return None
    return ParsedMarkdownFile(
        path=path,
        source_ref=path.relative_to(project_root).as_posix(),
        meta=meta,
        body=body,
    )


def parse_frontmatter(path: str | Path) -> tuple[dict | None, str | None]:
    """Read a Markdown file from disk and split off its YAML frontmatter.

    Convenience wrapper around :func:`split_frontmatter` for one-shot
    use without managing a :class:`DiagnosticBag` directly.

    :param path: Filesystem path to a ``.md`` file (UTF-8 expected).
    :returns: ``(meta_dict, body_str)`` on success;
        ``(None, None)`` on read or parse failure.
    """
    diagnostics = DiagnosticBag()
    file_path = Path(path)
    text = read_utf8_text(file_path, diagnostics)
    if text is None:
        return None, None
    return split_frontmatter(text, file_path, diagnostics)


def validate_project_relative_path(
    raw_value: object,
    project_root: Path,
    base_dir: Path,
    diagnostics: DiagnosticBag,
    label: str,
    source: Path | str,
    allow_markdown_only: bool = False,
) -> tuple[Path, str] | None:
    raw_text = trimmed_string(raw_value)
    if raw_text is None:
        diagnostics.error(f"{label} path is empty", source)
        return None
    normalized = normalize_path_string(raw_text)
    if is_absolute_reference(normalized):
        diagnostics.error("Absolute paths MUST produce an error", source)
        return None
    pure = PurePosixPath(normalized)
    if any(part == ".." for part in pure.parts):
        diagnostics.error("Path traversal (`..` segments) is forbidden", source)
        return None
    if any(part.startswith(".") for part in pure.parts):
        diagnostics.error("Hidden files and directories are not valid ProseDown source paths", source)
        return None
    if any(part.startswith("_") for part in pure.parts):
        diagnostics.error("Draft files are excluded from the build", source)
        return None
    candidate = (base_dir / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        diagnostics.error("Files outside the project root are forbidden", source)
        return None
    if allow_markdown_only and candidate.suffix != ".md":
        diagnostics.error(f"{label} must point to a .md file", source)
        return None
    return candidate, pure.as_posix()


def check_case_collisions(project_root: Path, diagnostics: DiagnosticBag) -> None:
    seen: dict[str, str] = {}
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(project_root).as_posix()
        lower = rel.lower()
        if lower in seen and seen[lower] != rel:
            diagnostics.warn("Files differ only by case", rel)
        else:
            seen[lower] = rel


def discover_chapters(project_root: Path, diagnostics: DiagnosticBag) -> list[Path] | None:
    discovered: list[tuple[int, str, Path]] = []
    seen_numbers: dict[int, str] = {}
    for path in sorted(project_root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.name == "book.md" or path.name.startswith(".") or path.name.startswith("_"):
            continue
        if path.suffix != ".md":
            continue
        match = AUTO_DISCOVERY_RE.fullmatch(path.name)
        if not match:
            diagnostics.warn("File not included — add numeric prefix or list in chapters:", path.name)
            continue
        prefix = match.group(1)
        number = int(prefix)
        if len(prefix) == 1:
            diagnostics.warn("Consider zero-padding: 01- instead of 1-", path.name)
        if number in seen_numbers:
            diagnostics.error("Duplicate numeric prefixes are ambiguous", path.name)
            diagnostics.error("Duplicate numeric prefixes are ambiguous", seen_numbers[number])
            return None
        seen_numbers[number] = path.name
        discovered.append((number, path.name, path))
    discovered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in discovered]


def resolve_chapter_paths(project_root: Path, book_meta: dict, diagnostics: DiagnosticBag) -> list[Path] | None:
    chapter_list = book_meta.get("chapters")
    if chapter_list == []:
        chapter_list = None
    if chapter_list is None:
        return discover_chapters(project_root, diagnostics)
    if not isinstance(chapter_list, list):
        diagnostics.error("chapters must be a list", project_root / "book.md")
        return None

    resolved: list[Path] = []
    seen_refs: set[str] = set()
    for raw_entry in chapter_list:
        result = validate_project_relative_path(
            raw_entry,
            project_root,
            project_root,
            diagnostics,
            "chapters entry",
            project_root / "book.md",
            allow_markdown_only=True,
        )
        if result is None:
            return None
        path, rel = result
        if rel == "book.md":
            diagnostics.error("book.md MUST NOT appear in chapters:", project_root / "book.md")
            return None
        if rel in seen_refs:
            diagnostics.error("Duplicate entry in chapters:", project_root / "book.md")
            return None
        if not path.exists():
            diagnostics.error("File listed in chapters: doesn't exist", rel)
            return None
        seen_refs.add(rel)
        resolved.append(path)

    root_markdown = {
        path.name
        for path in project_root.iterdir()
        if path.is_file()
        and path.suffix == ".md"
        and path.name != "book.md"
        and not path.name.startswith(".")
        and not path.name.startswith("_")
    }
    listed_root = {path.name for path in resolved if path.parent == project_root}
    for unlisted in sorted(root_markdown - listed_root):
        diagnostics.warn("File not included — add numeric prefix or list in chapters:", unlisted)
    return resolved


def first_h1_from_soup(soup: BeautifulSoup) -> str | None:
    heading = soup.find("h1")
    if not heading:
        return None
    text = nfc(heading.get_text(" ", strip=True)).strip()
    return text or None


def count_duplicate_footnotes(markdown_text: str) -> list[str]:
    labels = FOOTNOTE_DEF_RE.findall(markdown_text)
    duplicates = [label for label, count in Counter(labels).items() if count > 1]
    return sorted(duplicates)


def normalize_boolean(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return None


def language_quote_style(language: str) -> tuple[str, str, str, str, bool]:
    lowered = (language or "en").lower()
    if lowered.startswith("fr"):
        return "«\u00a0", "\u00a0»", "‹\u00a0", "\u00a0›", True
    if lowered.startswith("de"):
        return "„", "“", "‚", "‘", True
    if lowered.startswith("en"):
        return "“", "”", "‘", "’", True
    return "“", "”", "‘", "’", False


def smartypants_segment(text: str, language: str) -> tuple[str, bool]:
    open_double, close_double, open_single, close_single, supported = language_quote_style(language)
    text = text.replace("...", "…")
    text = text.replace("---", "\uFFFFEMDASH\uFFFF")
    text = text.replace("--", "–")
    text = text.replace("\uFFFFEMDASH\uFFFF", "—")
    # Convert feet/inches patterns before quote logic.
    text = re.sub(r"(?<!\w)(\d+)'(\s*)(\d{1,2})\"", r"\1′\2\3″", text)

    chars: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        prev_char = text[i - 1] if i > 0 else ""
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if char == "'" and next_char and next_char.isalnum() and (
            not prev_char or prev_char.isspace() or prev_char in "([{\u2014\u2013\""
        ):
            chars.append("’")
        elif char == "'" and prev_char.isalnum() and next_char.isalnum():
            chars.append("’")
        elif char == '"':
            opener = not prev_char or prev_char.isspace() or prev_char in "([{\u2014\u2013"
            chars.append(open_double if opener else close_double)
        elif char == "'":
            opener = not prev_char or prev_char.isspace() or prev_char in "([{\u2014\u2013"
            chars.append(open_single if opener else close_single)
        else:
            chars.append(char)
        i += 1
    return "".join(chars), supported


def apply_smart_typography(soup: BeautifulSoup, language: str) -> bool:
    supported = True
    excluded = {"code", "pre", "script", "style"}
    for text_node in list(soup.find_all(string=True)):
        parent = text_node.parent
        if parent is None:
            continue
        ancestors = [parent] + list(parent.parents)
        if any(getattr(ancestor, "name", None) in excluded for ancestor in ancestors):
            continue
        if parent.name == "a":
            node_text = text_node.strip()
            href = parent.get("href", "")
            if URLISH_RE.fullmatch(node_text) or node_text == href:
                continue
        original = str(text_node)
        pieces: list[str] = []
        last = 0
        local_supported = True
        for match in URLISH_RE.finditer(original):
            if match.start() > last:
                transformed, ok = smartypants_segment(original[last:match.start()], language)
                pieces.append(transformed)
                local_supported = local_supported and ok
            pieces.append(match.group(0))
            last = match.end()
        if last < len(original):
            transformed, ok = smartypants_segment(original[last:], language)
            pieces.append(transformed)
            local_supported = local_supported and ok
        updated = "".join(pieces)
        supported = supported and local_supported
        if updated != original:
            text_node.replace_with(updated)
    return supported


def strip_event_handler_attrs(tag: Tag) -> None:
    for attr in list(tag.attrs.keys()):
        if EVENT_ATTR_RE.match(attr):
            del tag.attrs[attr]


def validate_raw_html_resources(tag: Tag, diagnostics: DiagnosticBag, source: str | Path) -> None:
    if tag.name in {"img", "source", "audio", "video"} and is_remote_url(tag.get("src")):
        diagnostics.error("Remote image URL in Markdown", source)
    if tag.name == "img" and is_remote_url(tag.get("srcset")):
        diagnostics.error("Remote image URL in Markdown", source)
    if tag.name == "link" and is_remote_url(tag.get("href")):
        diagnostics.error("External resource references in raw HTML are forbidden", source)


def heading_id_uniqueness(soup: BeautifulSoup, diagnostics: DiagnosticBag, source: str | Path) -> tuple[set[str], list[HeadingEntry], str | None]:
    headings = list(soup.find_all(re.compile(r"^h[1-6]$")))
    h1_count = sum(1 for heading in headings if heading.name == "h1")
    if h1_count > 1:
        diagnostics.warn("Only the first H1 is used; additional H1s are ignored", source)
    previous_level = None
    used_ids: Counter[str] = Counter()
    entries: list[HeadingEntry] = []
    stack: list[HeadingEntry] = []
    first_h1_text = None
    for heading in headings:
        level = int(heading.name[1])
        text = nfc(heading.get_text(" ", strip=True)).strip() or "Section"
        if level == 1 and first_h1_text is None:
            first_h1_text = text
        base = slugify(text)
        used_ids[base] += 1
        assigned = base if used_ids[base] == 1 else f"{base}-{used_ids[base]}"
        heading["id"] = assigned
        if previous_level is not None and level > previous_level + 1:
            diagnostics.warn("Heading jumps from H1 to H3 — affects accessibility", source)
        previous_level = level
        entry = HeadingEntry(level=level, text=text, anchor=assigned)
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            stack[-1].children.append(entry)
        else:
            entries.append(entry)
        stack.append(entry)
    return {heading["id"] for heading in headings if heading.get("id")}, entries, first_h1_text


def transform_captioned_images(
    soup: BeautifulSoup,
    project_root: Path,
    base_dir: Path,
    diagnostics: DiagnosticBag,
    source: str | Path,
) -> set[str]:
    used_assets: set[str] = set()
    for img in list(soup.find_all("img")):
        strip_event_handler_attrs(img)
        validate_raw_html_resources(img, diagnostics, source)
        src = img.get("src")
        if src:
            parsed_src = urlparse(src)
            source_path = parsed_src.path or src
            validated = validate_project_relative_path(source_path, project_root, base_dir, diagnostics, "image", source)
            if validated is not None:
                _, rel = validated
                used_assets.add(rel)
                suffix = ""
                if parsed_src.query:
                    suffix += f"?{parsed_src.query}"
                if parsed_src.fragment:
                    suffix += f"#{parsed_src.fragment}"
                img["src"] = f"../{rel}{suffix}"
        if not img.has_attr("alt"):
            diagnostics.warn("Missing alt text affects accessibility", source)
            img["alt"] = ""
        elif img.get("alt", "") == "":
            diagnostics.warn("Missing alt text affects accessibility", source)
        title = img.get("title")
        if not title:
            continue
        del img["title"]
        figure = soup.new_tag("figure")
        caption = soup.new_tag("figcaption")
        caption.string = title
        parent = img.parent
        if parent and parent.name == "p":
            non_ws_children = [child for child in parent.contents if not isinstance(child, NavigableString) or child.strip()]
            if len(non_ws_children) == 1 and non_ws_children[0] is img:
                parent.replace_with(figure)
                figure.append(img)
            else:
                img.wrap(figure)
        else:
            img.wrap(figure)
        figure.append(caption)
    return used_assets


def transform_footnotes(soup: BeautifulSoup, diagnostics: DiagnosticBag, source: str | Path) -> set[str]:
    label_to_number: dict[str, int] = {}
    seen_numbers = 0
    anchor_ids: set[str] = set()

    for ref in soup.select("sup a.footnote-ref, a.footnote-ref"):
        href = ref.get("href", "")
        label = href.split(":", 1)[1] if ":" in href else href.lstrip("#fn-")
        if label not in label_to_number:
            seen_numbers += 1
            label_to_number[label] = seen_numbers
        number = label_to_number[label]
        ref.attrs = {}
        ref.clear()
        ref.string = str(number)
        ref["href"] = f"#fn-{number}"
        ref["id"] = f"fnref-{number}"
        ref["epub:type"] = "noteref"
        ref["role"] = "doc-noteref"
        anchor_ids.add(ref["id"])
        if ref.parent and ref.parent.name == "sup":
            ref.parent.attrs = {}

    footnote_div = soup.find("div", class_="footnote")
    if footnote_div:
        asides: list[Tag] = []
        for li in footnote_div.select("ol > li"):
            li_id = li.get("id", "")
            label = li_id.split(":", 1)[1] if ":" in li_id else li_id.lstrip("fn-")
            if label not in label_to_number:
                seen_numbers += 1
                label_to_number[label] = seen_numbers
            number = label_to_number[label]
            aside = soup.new_tag("aside")
            aside["epub:type"] = "footnote"
            aside["role"] = "doc-footnote"
            aside["id"] = f"fn-{number}"
            anchor_ids.add(aside["id"])
            paragraphs = li.find_all("p", recursive=False) or [li]
            for index, paragraph in enumerate(paragraphs):
                new_p = soup.new_tag("p")
                if index == 0:
                    backlink = soup.new_tag("a", href=f"#fnref-{number}")
                    backlink["role"] = "doc-backlink"
                    backlink.string = f"{number}."
                    new_p.append(backlink)
                    new_p.append(" ")
                for child in list(paragraph.contents):
                    if isinstance(child, Tag) and "footnote-backref" in child.get("class", []):
                        continue
                    new_p.append(child.extract() if isinstance(child, Tag) else child)
                if new_p.contents and isinstance(new_p.contents[-1], NavigableString):
                    new_p.contents[-1].replace_with(str(new_p.contents[-1]).rstrip())
                aside.append(new_p)
            asides.append(aside)
        footnote_div.replace_with(*asides)

    return anchor_ids


def rewrite_internal_links(
    soup: BeautifulSoup,
    doc: BuildDocument,
    project_root: Path,
    link_map: dict[str, str],
    diagnostics: DiagnosticBag,
) -> list[str]:
    hrefs: list[str] = []
    base_dir = doc.source_path.parent if doc.source_path is not None else project_root
    for tag in soup.find_all("a", href=True):
        strip_event_handler_attrs(tag)
        href = tag.get("href", "").strip()
        hrefs.append(href)
        if not href or href.startswith("#"):
            continue
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme not in {"mailto"}:
            continue
        if parsed.path.endswith(".md"):
            validated = validate_project_relative_path(parsed.path, project_root, base_dir, diagnostics, "link", doc.source_ref)
            if validated is None:
                continue
            _, rel = validated
            if rel not in link_map:
                diagnostics.error("Broken internal links MUST produce an error", doc.source_ref)
                continue
            fragment = f"#{parsed.fragment}" if parsed.fragment else ""
            tag["href"] = f"{link_map[rel]}{fragment}"
    return hrefs


def render_markdown_document(
    doc: BuildDocument,
    project_root: Path,
    language: str,
    link_map: dict[str, str],
    diagnostics: DiagnosticBag,
) -> None:
    duplicates = count_duplicate_footnotes(doc.body_markdown)
    if duplicates:
        diagnostics.error("Duplicate labels within the same file MUST produce an error", doc.source_ref)
        return

    html_fragment = markdown.markdown(doc.body_markdown or "", extensions=MARKDOWN_EXTENSIONS, output_format="xhtml")
    soup = BeautifulSoup(html_fragment, "html.parser")

    for script in list(soup.find_all("script")):
        script.decompose()
    for tag in soup.find_all(True):
        strip_event_handler_attrs(tag)
        validate_raw_html_resources(tag, diagnostics, doc.source_ref)

    doc.declared_title = trimmed_string(doc.meta.get("title"))
    doc.authors = normalize_author_list(doc.meta.get("author"))
    doc.toc_override = normalize_boolean(doc.meta.get("toc"))

    used_assets = transform_captioned_images(
        soup,
        project_root,
        doc.source_path.parent if doc.source_path is not None else project_root,
        diagnostics,
        doc.source_ref,
    )
    footnote_anchor_ids = transform_footnotes(soup, diagnostics, doc.source_ref)
    heading_ids, heading_entries, first_heading = heading_id_uniqueness(soup, diagnostics, doc.source_ref)
    doc.first_heading = first_heading
    doc.title = title_resolution(doc.declared_title, first_heading, doc.source_slug)
    if doc.declared_title and first_heading and doc.declared_title != first_heading:
        diagnostics.warn("TOC uses frontmatter title; heading renders in body", doc.source_ref)
    if first_heading is None:
        diagnostics.warn("Title derived from filename — consider adding a heading", doc.source_ref)
        generated = soup.new_tag("h1")
        generated.string = doc.title
        generated["id"] = slugify(doc.title)
        if soup.contents:
            soup.insert(0, generated)
        else:
            soup.append(generated)
        heading_ids, heading_entries, first_heading = heading_id_uniqueness(soup, diagnostics, doc.source_ref)
        doc.first_heading = first_heading
    supported = apply_smart_typography(soup, language)
    if not supported:
        diagnostics.warn("Falling back to English-style quotes", doc.source_ref)
    doc.links = rewrite_internal_links(soup, doc, project_root, link_map, diagnostics)
    doc.used_assets = used_assets
    doc.anchor_ids = heading_ids | footnote_anchor_ids
    doc.heading_entries = heading_entries
    doc.html_body = "".join(str(node) for node in soup.contents)


def heading_entries_for_toc(doc: BuildDocument, toc_depth: int) -> list[HeadingEntry]:
    if toc_depth <= 1:
        return []
    result: list[HeadingEntry] = []
    for entry in doc.heading_entries:
        if entry.level != 1:
            continue
        result.extend(_heading_children_for_depth(entry.children, toc_depth))
    return result


def _heading_children_for_depth(entries: list[HeadingEntry], toc_depth: int) -> list[HeadingEntry]:
    kept: list[HeadingEntry] = []
    for entry in entries:
        if entry.level > toc_depth:
            continue
        kept.append(
            HeadingEntry(
                level=entry.level,
                text=entry.text,
                anchor=entry.anchor,
                children=_heading_children_for_depth(entry.children, toc_depth),
            )
        )
    return kept


def validate_document_links(doc: BuildDocument, doc_map: dict[str, BuildDocument], diagnostics: DiagnosticBag) -> None:
    for href in doc.links:
        if not href:
            continue
        if href.startswith("#"):
            target = href[1:]
            if target and target not in doc.anchor_ids:
                diagnostics.error("Broken internal links MUST produce an error", doc.source_ref)
            continue
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme not in {"mailto"}:
            continue
        if parsed.path.endswith(".xhtml"):
            target_doc = doc_map.get(parsed.path)
            if target_doc is None:
                diagnostics.error("Broken internal links MUST produce an error", doc.source_ref)
                continue
            if parsed.fragment and parsed.fragment not in target_doc.anchor_ids:
                diagnostics.error("Broken internal links MUST produce an error", doc.source_ref)


def output_stem_for_source(source_ref: str, source_slug: str, used: set[str]) -> str:
    base = slugify(source_slug)
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def parse_book_metadata(meta: dict, diagnostics: DiagnosticBag, source: Path | str) -> tuple[str, list[str], str] | None:
    title = trimmed_string(meta.get("title"))
    if title is None:
        diagnostics.error("Missing title or author", source)
        return None
    authors = normalize_author_list(meta.get("author"))
    if not authors:
        diagnostics.error("Missing title or author", source)
        return None
    language = trimmed_string(meta.get("language")) or "en"
    return title, authors, language


def normalize_optional_scalar(meta: dict, key: str) -> str | None:
    return trimmed_string(meta.get(key))


def normalize_subjects(meta: dict) -> list[str]:
    value = meta.get("subject")
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in (trimmed_string(item) for item in value) if item]
    single = trimmed_string(value)
    return [single] if single else []


def contributor_groups(meta: dict) -> dict[str, list[str]]:
    return {
        "aut": normalize_author_list(meta.get("author")),
        "edt": normalize_author_list(meta.get("editor")),
        "trl": normalize_author_list(meta.get("translator")),
        "ill": normalize_author_list(meta.get("illustrator")),
    }


def primary_identifier(meta: dict, title: str, authors: list[str], language: str) -> str:
    identifier = normalize_optional_scalar(meta, "identifier")
    isbn = normalize_optional_scalar(meta, "isbn")
    if identifier:
        return identifier
    if isbn:
        return f"urn:isbn:{isbn}"
    return deterministic_uuid(title, authors, language)


def build_cover_warning(path: Path, diagnostics: DiagnosticBag) -> None:
    size = image_dimensions(path)
    if size is None:
        return
    width, height = size
    if max(width, height) < 1400:
        diagnostics.warn("Recommended minimum 1600×2560 for retail", path)


def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    suffix = path.suffix.lower()
    if suffix == ".png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if suffix in {".jpg", ".jpeg"} and data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(data[index + 5:index + 7], "big")
                width = int.from_bytes(data[index + 7:index + 9], "big")
                return width, height
            if marker == 0xDA:
                break
            segment = int.from_bytes(data[index + 2:index + 4], "big")
            index += 2 + segment
    if suffix == ".gif" and data[:6] in {b"GIF87a", b"GIF89a"}:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if suffix == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        if kind == b"VP8 ":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        if kind == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
    return None


def choose_cover(project_root: Path, book_meta: dict, diagnostics: DiagnosticBag) -> tuple[Path, str] | None:
    candidates: list[tuple[Path, str]] = []
    cover_override = book_meta.get("cover")
    if cover_override is not None:
        validated = validate_project_relative_path(cover_override, project_root, project_root, diagnostics, "cover", project_root / "book.md")
        if validated is not None:
            path, rel = validated
            candidates.append((path, rel))
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        path = project_root / f"cover{suffix}"
        if path.exists():
            candidates.append((path, path.relative_to(project_root).as_posix()))
    for path, rel in candidates:
        if path.exists() and path.is_file():
            build_cover_warning(path, diagnostics)
            return path, rel
    return None


def choose_css(project_root: Path, book_meta: dict, diagnostics: DiagnosticBag) -> tuple[Path | None, str, bytes]:
    output_href = "css/style.css"
    css_override = book_meta.get("css")
    if css_override is not None:
        validated = validate_project_relative_path(css_override, project_root, project_root, diagnostics, "css", project_root / "book.md")
        if validated is None:
            return None, output_href, b""
        css_path, _rel = validated
        if not css_path.exists():
            diagnostics.error("Custom CSS file doesn't exist", css_path)
            return None, output_href, b""
        text = read_utf8_text(css_path, diagnostics)
        return css_path, output_href, (text or "").encode("utf-8")
    conventional = project_root / "css" / "style.css"
    if conventional.exists():
        text = read_utf8_text(conventional, diagnostics)
        return conventional, output_href, (text or "").encode("utf-8")
    label, text = _read_packaged_default_css()
    return Path(label), output_href, text.encode("utf-8")


def _read_packaged_default_css() -> tuple[str, str]:
    """Return (label, text) for the bundled default stylesheet.

    The CSS ships as package data at `prosedown/data/prosedown-default.css`.
    We read it via `importlib.resources` so it works whether the package is
    installed from a wheel, a source dist, an editable install, or run
    in-place from a checkout. The returned label is the resource path for
    diagnostics; it's not a real filesystem path inside a wheel but is
    informative.
    """
    from importlib.resources import files

    resource = files(__package__).joinpath("data", "prosedown-default.css")
    return f"<package:prosedown/data/prosedown-default.css>", resource.read_text(encoding="utf-8")


def modified_timestamp(paths: Iterable[Path]) -> datetime:
    mtimes = [path.stat().st_mtime for path in paths if path.exists()]
    if not mtimes:
        return datetime.now(timezone.utc).replace(microsecond=0)
    return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).replace(microsecond=0)


def gather_build_documents(project_root: Path, diagnostics: DiagnosticBag) -> tuple[dict, list[BuildDocument], list[Path]] | None:
    check_case_collisions(project_root, diagnostics)
    book_file = load_markdown_file(project_root / "book.md", project_root, diagnostics)
    if book_file is None:
        return None
    metadata = parse_book_metadata(book_file.meta, diagnostics, book_file.path)
    if metadata is None:
        return None
    book_title, book_authors, language = metadata
    chapter_paths = resolve_chapter_paths(project_root, book_file.meta, diagnostics)
    if chapter_paths is None:
        return None

    used_output_stems: set[str] = set()
    documents: list[BuildDocument] = []
    source_paths: list[Path] = [book_file.path]

    if trimmed_string(book_file.body):
        intro_slug = "book-intro"
        body_epub_type, section_epub_type, section_aria_role = role_to_types("frontmatter", intro_slug)
        intro_stem = output_stem_for_source("book.md", intro_slug, used_output_stems)
        documents.append(
            BuildDocument(
                source_ref="book.md",
                source_path=book_file.path,
                source_slug=intro_slug,
                output_stem=intro_stem,
                file_name=f"{intro_stem}.xhtml",
                meta={},
                body_markdown=book_file.body,
                title=book_title,
                role="frontmatter",
                include_in_toc=False,
                toc_override=None,
                authors=book_authors,
                language=language,
                body_epub_type=body_epub_type,
                section_epub_type=section_epub_type,
                section_aria_role=section_aria_role,
            )
        )

    for chapter_path in chapter_paths:
        parsed = load_markdown_file(chapter_path, project_root, diagnostics)
        if parsed is None:
            return None
        source_paths.append(parsed.path)
        basename = chapter_path.stem
        if AUTO_DISCOVERY_RE.fullmatch(chapter_path.name):
            source_slug = re.sub(r"^\d+-", "", basename)
        else:
            source_slug = basename
        declared_role = trimmed_string(parsed.meta.get("role"))
        role = declared_role.lower() if declared_role else detect_role_from_slug(source_slug)
        chapter_language = trimmed_string(parsed.meta.get("language")) or language
        toc_override = normalize_boolean(parsed.meta.get("toc"))
        include_in_toc = toc_override if toc_override is not None else role != "frontmatter"
        body_epub_type, section_epub_type, section_aria_role = role_to_types(role, source_slug)
        output_stem = output_stem_for_source(parsed.source_ref, source_slug, used_output_stems)
        documents.append(
            BuildDocument(
                source_ref=parsed.source_ref,
                source_path=parsed.path,
                source_slug=source_slug,
                output_stem=output_stem,
                file_name=f"{output_stem}.xhtml",
                meta=parsed.meta,
                body_markdown=parsed.body,
                title=deslugify(source_slug),
                role=role,
                include_in_toc=include_in_toc,
                toc_override=toc_override,
                authors=normalize_author_list(parsed.meta.get("author")) or book_authors,
                language=chapter_language,
                body_epub_type=body_epub_type,
                section_epub_type=section_epub_type,
                section_aria_role=section_aria_role,
            )
        )

    if not documents:
        diagnostics.error("A multi-file project must contain book.md body content or at least one chapter file", project_root)
        return None

    return {"title": book_title, "authors": book_authors, "language": language, "book_meta": book_file.meta}, documents, source_paths


def gather_single_file_document(source_file: Path, diagnostics: DiagnosticBag) -> tuple[dict, list[BuildDocument], list[Path]] | None:
    parsed = load_markdown_file(source_file, source_file.parent, diagnostics)
    if parsed is None:
        return None
    metadata = parse_book_metadata(parsed.meta, diagnostics, source_file)
    if metadata is None:
        return None
    title, authors, language = metadata
    body_epub_type, section_epub_type, section_aria_role = role_to_types("chapter", slugify(title))
    document = BuildDocument(
        source_ref=source_file.name,
        source_path=source_file,
        source_slug=slugify(source_file.stem),
        output_stem="content",
        file_name="content.xhtml",
        meta=parsed.meta,
        body_markdown=parsed.body,
        title=title,
        role="chapter",
        include_in_toc=True,
        toc_override=True,
        authors=authors,
        language=language,
        body_epub_type=body_epub_type,
        section_epub_type=section_epub_type,
        section_aria_role=section_aria_role,
    )
    return {"title": title, "authors": authors, "language": language, "book_meta": parsed.meta}, [document], [source_file]


def toc_entries_for_documents(documents: list[BuildDocument], toc_depth: int, book_title: str, single_file: bool) -> list[TocEntry]:
    if toc_depth == 0:
        first_doc = documents[0]
        return [TocEntry(book_title, first_doc.file_name)]
    entries: list[TocEntry] = []
    current_part: TocEntry | None = None
    for doc in documents:
        if not doc.include_in_toc:
            continue
        child_entries = [
            TocEntry(child.text, f"{doc.file_name}#{child.anchor}", [convert_heading_child(doc.file_name, grandchild) for grandchild in child.children])
            for child in heading_entries_for_toc(doc, toc_depth)
        ]
        top_entry = TocEntry(doc.title, doc.file_name, child_entries)
        if doc.role == "part":
            if current_part is not None:
                entries.append(current_part)
            current_part = TocEntry(doc.title, doc.file_name, [])
            continue
        if current_part is not None and doc.role == "chapter":
            current_part.children.append(top_entry)
            continue
        if current_part is not None:
            entries.append(current_part)
            current_part = None
        entries.append(top_entry)
    if current_part is not None:
        entries.append(current_part)
    if single_file and not entries:
        return [TocEntry(book_title, documents[0].file_name)]
    return entries


def convert_heading_child(file_name: str, entry: HeadingEntry) -> TocEntry:
    return TocEntry(
        entry.text,
        f"{file_name}#{entry.anchor}",
        [convert_heading_child(file_name, child) for child in entry.children],
    )


def escape_xml_text(value: str) -> str:
    return html.escape(value, quote=False)


def xhtml_document(title: str, language: str, css_href: str, body_epub_type: str, section_epub_type: str, section_aria_role: str | None, body_html: str) -> bytes:
    section_attrs = [f'epub:type="{html.escape(section_epub_type, quote=True)}"']
    if section_aria_role:
        section_attrs.append(f'role="{html.escape(section_aria_role, quote=True)}"')
    doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{html.escape(language, quote=True)}">\n'
        "<head>\n"
        f"  <title>{escape_xml_text(title)}</title>\n"
        f'  <link rel="stylesheet" type="text/css" href="{html.escape(css_href, quote=True)}" />\n'
        "</head>\n"
        f'<body epub:type="{html.escape(body_epub_type, quote=True)}">\n'
        f"  <section {' '.join(section_attrs)}>\n"
        f"{indent_xml_fragment(body_html, '    ')}\n"
        "  </section>\n"
        "</body>\n"
        "</html>\n"
    )
    return doc.encode("utf-8")


def indent_xml_fragment(fragment: str, prefix: str) -> str:
    lines = fragment.splitlines() or [fragment]
    return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in lines)


def build_nav_xhtml(entries: list[TocEntry], language: str) -> bytes:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{html.escape(language, quote=True)}">\n'
        "<head>\n"
        "  <title>Table of Contents</title>\n"
        "</head>\n"
        "<body>\n"
        '  <nav epub:type="toc" role="doc-toc">\n'
        "    <h1>Table of Contents</h1>\n"
        f"{render_nav_list(entries, '    ')}\n"
        "  </nav>\n"
        "</body>\n"
        "</html>\n"
    )
    return body.encode("utf-8")


def render_nav_list(entries: list[TocEntry], indent: str) -> str:
    lines = [f"{indent}<ol>"]
    for entry in entries:
        lines.extend(render_nav_entry(entry, indent + "  "))
    lines.append(f"{indent}</ol>")
    return "\n".join(lines)


def render_nav_entry(entry: TocEntry, indent: str) -> list[str]:
    lines = [f"{indent}<li><a href=\"{html.escape(entry.href, quote=True)}\">{escape_xml_text(entry.title)}</a>"]
    if entry.children:
        lines.append(render_nav_list(entry.children, indent + "  "))
        lines.append(f"{indent}</li>")
    else:
        lines[-1] += "</li>"
    return lines


def build_ncx(entries: list[TocEntry], book_title: str, identifier: str, language: str) -> bytes:
    play_order = 1
    nav_map_parts: list[str] = []

    def render_entry(entry: TocEntry, depth: int = 1) -> None:
        nonlocal play_order
        current_order = play_order
        play_order += 1
        nav_map_parts.append(
            f'{"  " * depth}<navPoint id="navPoint-{current_order}" playOrder="{current_order}">\n'
            f'{"  " * (depth + 1)}<navLabel><text>{escape_xml_text(entry.title)}</text></navLabel>\n'
            f'{"  " * (depth + 1)}<content src="{html.escape(entry.href, quote=True)}" />'
        )
        if entry.children:
            nav_map_parts[-1] += "\n"
            for child in entry.children:
                render_entry(child, depth + 1)
            nav_map_parts.append(f'{"  " * depth}</navPoint>')
        else:
            nav_map_parts[-1] += f"\n{'  ' * depth}</navPoint>"

    for entry in entries:
        render_entry(entry)

    ncx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" '
        f'xml:lang="{html.escape(language, quote=True)}">\n'
        "  <head>\n"
        f'    <meta name="dtb:uid" content="{html.escape(identifier, quote=True)}" />\n'
        "  </head>\n"
        f"  <docTitle><text>{escape_xml_text(book_title)}</text></docTitle>\n"
        "  <navMap>\n"
        f"{chr(10).join(nav_map_parts)}\n"
        "  </navMap>\n"
        "</ncx>\n"
    )
    return ncx.encode("utf-8")


def build_opf(
    metadata: dict,
    documents: list[BuildDocument],
    nav_entries: list[TocEntry],
    css_href: str,
    has_images: bool,
    identifier: str,
    modified: datetime,
    cover_href: str | None,
    assets: list[ContentAsset],
) -> bytes:
    book_title = metadata["title"]
    authors = metadata["authors"]
    language = metadata["language"]
    book_meta = metadata["book_meta"]
    root = etree.Element(
        "package",
        nsmap={None: OPF_NS, "dc": DC_NS},
        attrib={"version": "3.0", "unique-identifier": "bookid", f"{{{XML_NS}}}lang": language},
    )
    metadata_el = etree.SubElement(root, "metadata")
    etree.SubElement(metadata_el, f"{{{DC_NS}}}identifier", id="bookid").text = identifier
    title_id = "title"
    etree.SubElement(metadata_el, f"{{{DC_NS}}}title", id=title_id).text = book_title

    subtitle = normalize_optional_scalar(book_meta, "subtitle")
    if subtitle:
        subtitle_id = "subtitle"
        etree.SubElement(metadata_el, f"{{{DC_NS}}}title", id=subtitle_id).text = subtitle
        etree.SubElement(metadata_el, "meta", refines=f"#{subtitle_id}", property="title-type").text = "subtitle"

    contributor_index = 1
    author_sort = normalize_optional_scalar(book_meta, "author-sort")
    seen_creators: set[tuple[str, str]] = set()
    extra_authors = []
    for doc in documents:
        for author in doc.authors:
            extra_authors.append(author)
    groups = contributor_groups(book_meta)
    groups["aut"] = authors + [author for author in extra_authors if author not in authors]
    for role_code, names in groups.items():
        for position, name in enumerate(names):
            key = (role_code, name)
            if key in seen_creators:
                continue
            seen_creators.add(key)
            creator_id = f"creator-{contributor_index}"
            contributor_index += 1
            etree.SubElement(metadata_el, f"{{{DC_NS}}}creator", id=creator_id).text = name
            etree.SubElement(metadata_el, "meta", refines=f"#{creator_id}", property="role", scheme="marc:relators").text = role_code
            if role_code == "aut" and position == 0 and author_sort:
                etree.SubElement(metadata_el, "meta", refines=f"#{creator_id}", property="file-as").text = author_sort

    etree.SubElement(metadata_el, f"{{{DC_NS}}}language").text = language

    optional_dc_fields = {
        "publisher": "publisher",
        "description": "description",
        "rights": "rights",
        "date": "date",
    }
    for key, dc_name in optional_dc_fields.items():
        value = normalize_optional_scalar(book_meta, key)
        if value:
            etree.SubElement(metadata_el, f"{{{DC_NS}}}{dc_name}").text = value

    subjects = normalize_subjects(book_meta)
    for subject in subjects:
        etree.SubElement(metadata_el, f"{{{DC_NS}}}subject").text = subject

    explicit_identifier = normalize_optional_scalar(book_meta, "identifier")
    isbn = normalize_optional_scalar(book_meta, "isbn")
    if isbn and explicit_identifier:
        etree.SubElement(metadata_el, f"{{{DC_NS}}}identifier").text = f"urn:isbn:{isbn}"
    elif isbn and not explicit_identifier and identifier != f"urn:isbn:{isbn}":
        etree.SubElement(metadata_el, f"{{{DC_NS}}}identifier").text = f"urn:isbn:{isbn}"

    series = book_meta.get("series")
    if isinstance(series, dict):
        series_name = trimmed_string(series.get("name"))
        series_number = trimmed_string(series.get("number"))
        if series_name:
            collection_id = "series-collection"
            etree.SubElement(metadata_el, "meta", id=collection_id, property="belongs-to-collection").text = series_name
            etree.SubElement(metadata_el, "meta", refines=f"#{collection_id}", property="collection-type").text = "series"
            if series_number:
                etree.SubElement(metadata_el, "meta", refines=f"#{collection_id}", property="group-position").text = series_number

    accessibility = book_meta.get("accessibility")
    has_accessibility_block = isinstance(accessibility, dict) and bool(accessibility)
    access_modes = ["textual"]
    if has_images:
        access_modes.append("visual")
    for access_mode in access_modes:
        etree.SubElement(metadata_el, "meta", property="schema:accessMode").text = access_mode
    etree.SubElement(metadata_el, "meta", property="schema:accessModeSufficient").text = "textual"
    features = ["readingOrder", "structuralNavigation", "tableOfContents"]
    if has_accessibility_block and isinstance(accessibility.get("features"), list):
        feature_values = [trimmed_string(value) for value in accessibility.get("features", [])]
        features = [value for value in feature_values if value]
    for feature in features:
        etree.SubElement(metadata_el, "meta", property="schema:accessibilityFeature").text = feature
    if has_accessibility_block:
        summary = trimmed_string(accessibility.get("summary"))
        if summary:
            etree.SubElement(metadata_el, "meta", property="schema:accessibilitySummary").text = summary
        conforms = trimmed_string(accessibility.get("conformsTo"))
        if conforms:
            etree.SubElement(metadata_el, "meta", property="dcterms:conformsTo").text = conforms
        hazards = accessibility.get("hazards")
        if isinstance(hazards, list):
            for hazard in [trimmed_string(item) for item in hazards]:
                if hazard:
                    etree.SubElement(metadata_el, "meta", property="schema:accessibilityHazard").text = hazard

    etree.SubElement(metadata_el, "meta", property="dcterms:modified").text = modified.isoformat().replace("+00:00", "Z")

    manifest = etree.SubElement(root, "manifest")
    etree.SubElement(manifest, "item", id="nav", href="text/nav.xhtml", **{"media-type": "application/xhtml+xml", "properties": "nav"})
    etree.SubElement(manifest, "item", id="ncx", href="toc.ncx", **{"media-type": "application/x-dtbncx+xml"})
    etree.SubElement(manifest, "item", id="style", href=css_href, **{"media-type": "text/css"})
    for index, doc in enumerate(documents, start=1):
        etree.SubElement(manifest, "item", id=f"doc-{index}", href=f"text/{doc.file_name}", **{"media-type": "application/xhtml+xml"})
    for index, asset in enumerate(assets, start=1):
        attrs = {"id": f"asset-{index}", "href": asset.href, "media-type": asset.media_type}
        if cover_href and asset.href == cover_href:
            attrs["properties"] = "cover-image"
        etree.SubElement(manifest, "item", **attrs)

    spine_attrs = {"toc": "ncx"}
    direction = normalize_optional_scalar(book_meta, "direction")
    if direction in {"ltr", "rtl"}:
        spine_attrs["page-progression-direction"] = direction
    spine = etree.SubElement(root, "spine", **spine_attrs)
    for index in range(1, len(documents) + 1):
        etree.SubElement(spine, "itemref", idref=f"doc-{index}")

    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)


def container_xml() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        "  <rootfiles>\n"
        '    <rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml" />\n'
        "  </rootfiles>\n"
        "</container>\n"
    ).encode("utf-8")


def zipinfo_for(path: str, modified: datetime, compress_type: int = zipfile.ZIP_DEFLATED) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path)
    dt = modified.astimezone(timezone.utc)
    info.date_time = (max(1980, dt.year), dt.month, dt.day, dt.hour, dt.minute, dt.second)
    info.compress_type = compress_type
    info.external_attr = 0o644 << 16
    return info


def write_epub_archive(output_path: Path, modified: datetime, files: list[tuple[str, bytes]], diagnostics: DiagnosticBag) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w") as zf:
            mimetype_info = zipinfo_for("mimetype", modified, zipfile.ZIP_STORED)
            zf.writestr(mimetype_info, b"application/epub+zip")
            for name, data in files:
                zf.writestr(zipinfo_for(name, modified), data)
    except OSError as exc:
        diagnostics.error(f"Unable to write EPUB: {exc}", output_path)
        return False
    return True


def build(project_path: str, output_path: str | None = None) -> bool:
    """Compile a ProseDown project to an EPUB 3.3 file.

    The primary public entry point. Accepts either a single ``.md`` file
    (single-file project) or a directory containing ``book.md`` plus
    numbered chapters (``01-foo.md``, ``02-bar.md``, …). Output is a
    valid, EPUBCheck-clean EPUB 3.3 archive.

    The build is **deterministic** — identical sources produce identical
    bytes (modulo timestamps), so commits diff cleanly and reproducible
    builds work.

    Pipeline:

    1. Resolve the project root (file → its parent dir; dir → itself).
    2. Read ``book.md`` (or the single file) for frontmatter — title,
       author, language, optional cover, optional CSS.
    3. Discover chapters by filename order if multi-file.
    4. Parse each chapter's frontmatter + body.
    5. Render Markdown → XHTML via :class:`MarkdownRenderer`.
    6. Emit the OPF manifest, NCX, navigation document.
    7. Pack everything into a ZIP per the EPUB 3.3 spec (mimetype
       file uncompressed and first; everything else deflated).

    :param project_path: Path to a ``.md`` file or project directory.
    :param output_path: Where to write the ``.epub``. Defaults to the
        project's slugified title in the project's parent directory.
    :returns: ``True`` if the build succeeded with no errors. Warnings
        do not cause a ``False`` return. Diagnostics are emitted to
        stdout/stderr regardless.
    """
    diagnostics = DiagnosticBag()
    input_path = Path(project_path).expanduser().resolve()
    if input_path.is_file():
        gathered = gather_single_file_document(input_path, diagnostics)
        project_root = input_path.parent
        single_file = True
    elif input_path.is_dir():
        book_md = input_path / "book.md"
        if not book_md.exists():
            diagnostics.error("A project directory must contain book.md", input_path)
            diagnostics.emit()
            return False
        gathered = gather_build_documents(input_path, diagnostics)
        project_root = input_path
        single_file = False
    else:
        diagnostics.error("Input path not found", input_path)
        diagnostics.emit()
        return False

    if gathered is None:
        diagnostics.emit()
        return False
    metadata, documents, source_paths = gathered
    title = metadata["title"]
    authors = metadata["authors"]
    language = metadata["language"]
    book_meta = metadata["book_meta"]

    cover_result = choose_cover(project_root, book_meta, diagnostics)
    cover_path = cover_href = None
    if cover_result is not None:
        cover_path, cover_href = cover_result
        source_paths.append(cover_path)

    css_path, css_href, css_bytes = choose_css(project_root, book_meta, diagnostics)
    if css_path is not None:
        source_paths.append(css_path)

    link_map = {doc.source_ref: doc.file_name for doc in documents}
    for doc in documents:
        render_markdown_document(doc, project_root, doc.language, link_map, diagnostics)
    doc_map = {doc.file_name: doc for doc in documents}
    for doc in documents:
        validate_document_links(doc, doc_map, diagnostics)

    if diagnostics.has_errors:
        diagnostics.emit()
        return False

    used_asset_paths: set[str] = set()
    for doc in documents:
        used_asset_paths |= doc.used_assets

    assets: list[ContentAsset] = []
    has_images = False
    if cover_path is not None and cover_href is not None:
        cover_bytes = cover_path.read_bytes()
        media_type = media_type_for_path(cover_path) or "image/jpeg"
        assets.append(ContentAsset(cover_href, cover_bytes, media_type))
        has_images = True
    for rel in sorted(used_asset_paths):
        asset_path = project_root / Path(rel)
        if not asset_path.exists():
            diagnostics.error("Referenced image does not exist", rel)
            continue
        media_type = media_type_for_path(asset_path)
        if not media_type:
            continue
        assets.append(ContentAsset(rel, asset_path.read_bytes(), media_type))
        if media_type.startswith("image/"):
            has_images = True
        source_paths.append(asset_path)

    if diagnostics.has_errors:
        diagnostics.emit()
        return False

    toc_depth_default = 1 if single_file else 2
    toc_depth = book_meta.get("toc-depth", toc_depth_default)
    try:
        toc_depth_value = int(toc_depth)
    except (TypeError, ValueError):
        toc_depth_value = toc_depth_default
    nav_entries = toc_entries_for_documents(documents, toc_depth_value, title, single_file)

    identifier = primary_identifier(book_meta, title, authors, language)
    modified = modified_timestamp(source_paths)
    document_files = [
        (
            f"EPUB/text/{doc.file_name}",
            xhtml_document(
                doc.title,
                doc.language,
                posixpath.relpath(css_href, "text"),
                doc.body_epub_type,
                doc.section_epub_type,
                doc.section_aria_role,
                doc.html_body,
            ),
        )
        for doc in documents
    ]

    files: list[tuple[str, bytes]] = [
        ("META-INF/container.xml", container_xml()),
        ("EPUB/text/nav.xhtml", build_nav_xhtml(nav_entries, language)),
        ("EPUB/toc.ncx", build_ncx(nav_entries, title, identifier, language)),
        ("EPUB/content.opf", build_opf(metadata, documents, nav_entries, css_href, has_images, identifier, modified, cover_href, assets)),
        (f"EPUB/{css_href}", css_bytes),
    ]
    files.extend(document_files)
    files.extend((f"EPUB/{asset.href}", asset.data) for asset in assets)

    output = Path(output_path).expanduser() if output_path else (
        input_path.with_suffix(".epub") if input_path.is_file() else input_path / f"{slugify(title)}.epub"
    )
    success = write_epub_archive(output.resolve(), modified, files, diagnostics)
    diagnostics.emit()
    return success and not diagnostics.has_errors


def parse_xml(data: bytes) -> etree._Element:
    parser = etree.XMLParser(recover=True, remove_blank_text=False)
    return etree.fromstring(data, parser=parser)


def epub_rootfile(zip_file: zipfile.ZipFile) -> str:
    container = parse_xml(zip_file.read("META-INF/container.xml"))
    rootfile = container.find(".//container:rootfile", XML_NAMESPACES)
    if rootfile is None:
        raise ValueError("container.xml missing rootfile")
    return rootfile.get("full-path")


def manifest_items(opf_root: etree._Element, opf_path: str) -> tuple[dict[str, dict], list[dict], dict[str, list[dict]]]:
    base_dir = PurePosixPath(opf_path).parent
    items: dict[str, dict] = {}
    by_href: dict[str, list[dict]] = defaultdict(list)
    manifest = opf_root.find("opf:manifest", XML_NAMESPACES)
    ordered_items: list[dict] = []
    if manifest is None:
        return items, ordered_items, by_href
    for item in manifest.findall("opf:item", XML_NAMESPACES):
        href = posixpath.normpath(posixpath.join(base_dir.as_posix(), item.get("href")))
        entry = {
            "id": item.get("id"),
            "href": href,
            "media_type": item.get("media-type") or "",
            "properties": set((item.get("properties") or "").split()),
        }
        items[entry["id"]] = entry
        ordered_items.append(entry)
        by_href[href].append(entry)
    return items, ordered_items, by_href


def parse_guide(opf_root: etree._Element, opf_path: str) -> dict[str, dict]:
    guide: dict[str, dict] = {}
    guide_el = opf_root.find("opf:guide", XML_NAMESPACES)
    if guide_el is None:
        return guide
    base_dir = PurePosixPath(opf_path).parent
    for ref in guide_el.findall("opf:reference", XML_NAMESPACES):
        href = ref.get("href", "")
        if not href:
            continue
        normalized = posixpath.normpath(posixpath.join(base_dir.as_posix(), href.split("#", 1)[0]))
        guide[normalized] = {"type": (ref.get("type") or "").lower(), "title": ref.get("title") or ""}
    return guide


def parse_nav_document(zip_file: zipfile.ZipFile, nav_href: str) -> tuple[dict[str, str], set[str], set[str]]:
    toc_titles: dict[str, str] = {}
    included_docs: set[str] = set()
    part_docs: set[str] = set()
    soup = BeautifulSoup(zip_file.read(nav_href), "xml")
    nav = None
    for candidate in soup.find_all("nav"):
        epub_type = candidate.get("epub:type") or candidate.get(f"{{{EPUB_NS}}}type") or ""
        if "toc" in epub_type.split():
            nav = candidate
            break
    if nav is None:
        return toc_titles, included_docs, part_docs
    base_dir = PurePosixPath(nav_href).parent.as_posix()

    def walk_list(node: Tag) -> None:
        for li in node.find_all("li", recursive=False):
            anchor = li.find("a", recursive=False)
            if anchor and anchor.get("href"):
                raw_href = anchor["href"]
                href_path = posixpath.normpath(posixpath.join(base_dir, raw_href.split("#", 1)[0]))
                included_docs.add(href_path)
                toc_titles.setdefault(href_path, anchor.get_text(" ", strip=True))
                child_ol = li.find("ol", recursive=False)
                if child_ol:
                    child_docs = []
                    for nested_anchor in child_ol.find_all("a"):
                        nested_href = nested_anchor.get("href", "")
                        if not nested_href:
                            continue
                        child_docs.append(posixpath.normpath(posixpath.join(base_dir, nested_href.split("#", 1)[0])))
                    if any(child_doc != href_path for child_doc in child_docs):
                        part_docs.add(href_path)
                    walk_list(child_ol)

    top_ol = nav.find("ol")
    if top_ol:
        walk_list(top_ol)
    return toc_titles, included_docs, part_docs


def parse_ncx(zip_file: zipfile.ZipFile, ncx_href: str) -> dict[str, str]:
    titles: dict[str, str] = {}
    root = parse_xml(zip_file.read(ncx_href))
    base_dir = PurePosixPath(ncx_href).parent.as_posix()
    for nav_point in root.findall(".//ncx:navPoint", XML_NAMESPACES):
        content = nav_point.find("ncx:content", XML_NAMESPACES)
        label = nav_point.find(".//ncx:text", XML_NAMESPACES)
        if content is None or label is None:
            continue
        src = content.get("src", "")
        href = posixpath.normpath(posixpath.join(base_dir, src.split("#", 1)[0]))
        titles.setdefault(href, label.text or "")
    return titles


def text_content_without_tags(value: str | None) -> str | None:
    if value is None:
        return None
    soup = BeautifulSoup(html.unescape(value), "html.parser")
    text = nfc(soup.get_text(" ", strip=True)).strip()
    return text or None


def parse_epub_metadata(opf_root: etree._Element) -> dict:
    package_unique_id = opf_root.get("unique-identifier")
    metadata_el = opf_root.find("opf:metadata", XML_NAMESPACES)
    result: dict = {}
    if metadata_el is None:
        return result

    meta_by_ref: dict[str, list[etree._Element]] = defaultdict(list)
    named_meta: list[etree._Element] = []
    prop_meta: list[etree._Element] = []
    for meta in metadata_el.findall("opf:meta", XML_NAMESPACES):
        ref = (meta.get("refines") or "").lstrip("#")
        if ref:
            meta_by_ref[ref].append(meta)
        prop_meta.append(meta)
        named_meta.append(meta)

    title_elements = metadata_el.findall("dc:title", XML_NAMESPACES)
    for title_el in title_elements:
        title_id = title_el.get("id") or ""
        title_type = None
        for meta in meta_by_ref.get(title_id, []):
            if meta.get("property") == "title-type":
                title_type = trimmed_string(meta.text)
        if title_type == "subtitle":
            subtitle = trimmed_string(title_el.text)
            if subtitle:
                result["subtitle"] = subtitle
        else:
            title = trimmed_string(title_el.text)
            if title and "title" not in result:
                result["title"] = title

    creators = []
    editors = []
    translators = []
    illustrators = []
    author_sort = None
    for creator_el in metadata_el.findall("dc:creator", XML_NAMESPACES):
        name = trimmed_string(creator_el.text)
        if not name:
            continue
        creator_id = creator_el.get("id") or ""
        roles = []
        if creator_el.get(f"{{{OPF_NS}}}role"):
            roles.append(creator_el.get(f"{{{OPF_NS}}}role"))
        file_as = creator_el.get(f"{{{OPF_NS}}}file-as")
        for meta in meta_by_ref.get(creator_id, []):
            if meta.get("property") == "role":
                role_value = trimmed_string(meta.text)
                if role_value:
                    roles.append(role_value)
            elif meta.get("property") == "file-as":
                file_as = trimmed_string(meta.text) or file_as
        role_set = {role for role in roles if role}
        if not role_set or "aut" in role_set:
            creators.append(name)
            if author_sort is None and file_as:
                author_sort = file_as
        elif "edt" in role_set:
            editors.append(name)
        elif "trl" in role_set:
            translators.append(name)
        elif "ill" in role_set:
            illustrators.append(name)

    if creators:
        result["author"] = creators[0] if len(creators) == 1 else creators
    if author_sort:
        result["author-sort"] = author_sort
    if editors:
        result["editor"] = editors[0] if len(editors) == 1 else editors
    if translators:
        result["translator"] = translators[0] if len(translators) == 1 else translators
    if illustrators:
        result["illustrator"] = illustrators[0] if len(illustrators) == 1 else illustrators

    language_el = metadata_el.find("dc:language", XML_NAMESPACES)
    if language_el is not None:
        language = trimmed_string(language_el.text)
        if language:
            result["language"] = language

    for key in ("publisher", "rights", "date"):
        el = metadata_el.find(f"dc:{key}", XML_NAMESPACES)
        if el is not None:
            value = trimmed_string(el.text)
            if value:
                result[key] = value

    description_el = metadata_el.find("dc:description", XML_NAMESPACES)
    if description_el is not None:
        description = text_content_without_tags(description_el.text)
        if description:
            result["description"] = description

    subjects = [trimmed_string(el.text) for el in metadata_el.findall("dc:subject", XML_NAMESPACES)]
    subjects = [subject for subject in subjects if subject]
    if subjects:
        result["subject"] = subjects if len(subjects) > 1 else subjects[0]

    identifiers = []
    primary_identifier = None
    for identifier_el in metadata_el.findall("dc:identifier", XML_NAMESPACES):
        identifier_text = trimmed_string(identifier_el.text)
        if not identifier_text:
            continue
        identifier_id = identifier_el.get("id") or ""
        scheme = identifier_el.get(f"{{{OPF_NS}}}scheme") or ""
        identifiers.append((identifier_text, scheme, identifier_id))
        if package_unique_id and identifier_id == package_unique_id:
            primary_identifier = identifier_text

    isbn = None
    for value, scheme, _identifier_id in identifiers:
        digits = re.sub(r"[^0-9Xx]", "", value)
        if value.lower().startswith("urn:isbn:") or scheme.lower() == "isbn" or len(digits) in {10, 13}:
            isbn = value.removeprefix("urn:isbn:")
            break
    if isbn:
        result["isbn"] = isbn
    if primary_identifier and (not isbn or primary_identifier.lower() != f"urn:isbn:{isbn}".lower()):
        result["identifier"] = primary_identifier

    for meta in prop_meta:
        if meta.get("property") == "belongs-to-collection":
            collection_id = meta.get("id") or ""
            series_name = trimmed_string(meta.text)
            series_number = None
            if collection_id:
                for refinement in meta_by_ref.get(collection_id, []):
                    if refinement.get("property") == "collection-type" and trimmed_string(refinement.text) != "series":
                        series_name = None
                    if refinement.get("property") == "group-position":
                        series_number = trimmed_string(refinement.text)
            if series_name:
                result["series"] = {"name": series_name}
                if series_number is not None:
                    result["series"]["number"] = series_number
                break

    accessibility: dict = {}
    feature_values = [trimmed_string(meta.text) for meta in prop_meta if meta.get("property") == "schema:accessibilityFeature"]
    feature_values = [value for value in feature_values if value]
    if feature_values:
        default_set = {"readingOrder", "structuralNavigation", "tableOfContents"}
        if set(feature_values) != default_set:
            accessibility["features"] = feature_values
    hazard_values = [trimmed_string(meta.text) for meta in prop_meta if meta.get("property") == "schema:accessibilityHazard"]
    hazard_values = [value for value in hazard_values if value]
    if hazard_values:
        accessibility["hazards"] = hazard_values
    summary_values = [trimmed_string(meta.text) for meta in prop_meta if meta.get("property") == "schema:accessibilitySummary"]
    if summary_values and summary_values[0]:
        accessibility["summary"] = summary_values[0]
    conforms_values = [trimmed_string(meta.text) for meta in prop_meta if meta.get("property") == "dcterms:conformsTo"]
    if conforms_values and conforms_values[0]:
        accessibility["conformsTo"] = conforms_values[0]
    if accessibility:
        result["accessibility"] = accessibility

    return result


def cover_href_from_opf(opf_root: etree._Element, manifest: dict[str, dict]) -> str | None:
    for item in manifest.values():
        if "cover-image" in item["properties"]:
            return item["href"]
    metadata_el = opf_root.find("opf:metadata", XML_NAMESPACES)
    if metadata_el is None:
        return None
    for meta in metadata_el.findall("opf:meta", XML_NAMESPACES):
        if (meta.get("name") or "").lower() == "cover":
            target_id = meta.get("content")
            if target_id and target_id in manifest:
                return manifest[target_id]["href"]
    return None


def spine_document_hrefs(opf_root: etree._Element, manifest: dict[str, dict]) -> list[str]:
    spine = opf_root.find("opf:spine", XML_NAMESPACES)
    if spine is None:
        return []
    hrefs: list[str] = []
    for itemref in spine.findall("opf:itemref", XML_NAMESPACES):
        idref = itemref.get("idref")
        if not idref or idref not in manifest:
            continue
        media_type = manifest[idref]["media_type"]
        if media_type == "application/xhtml+xml" and "nav" not in manifest[idref]["properties"]:
            hrefs.append(manifest[idref]["href"])
    return hrefs


def path_slug_from_href(href: str) -> str:
    stem = Path(PurePosixPath(href).name).stem
    return slugify(stem)


def extract_epub_type(tag: Tag | None) -> list[str]:
    if tag is None:
        return []
    for attr in ("epub:type", f"{{{EPUB_NS}}}type"):
        value = tag.get(attr)
        if value:
            return value.split()
    return []


def detect_role_from_document(
    href: str,
    soup: BeautifulSoup,
    guide: dict[str, dict],
    toc_part_docs: set[str],
) -> tuple[str, str]:
    if href in toc_part_docs:
        return "part", "part"

    body = soup.find("body")
    section = soup.find(["section", "article", "div"])
    for tag in (body, section):
        for epub_type in extract_epub_type(tag):
            role = EPUB_TYPE_TO_ROLE.get(epub_type)
            if role:
                slug = EPUB_TYPE_TO_SLUG.get(epub_type, path_slug_from_href(href))
                return role, slug

    guide_info = guide.get(href)
    if guide_info:
        guide_type = guide_info["type"]
        role = GUIDE_TYPE_TO_ROLE.get(guide_type)
        if role:
            return role, GUIDE_TYPE_TO_SLUG.get(guide_type, path_slug_from_href(href))

    filename_slug = path_slug_from_href(href)
    if "part" in (soup.find("body") or soup).get("class", []) or re.search(r"\bpart\b", " ".join((soup.find("body") or soup).get("class", []))):
        return "part", filename_slug
    return detect_role_from_slug(filename_slug), filename_slug


def detect_title_from_document(href: str, soup: BeautifulSoup, toc_titles: dict[str, str], guide: dict[str, dict], metadata_title: str | None) -> str | None:
    if href in toc_titles and toc_titles[href]:
        return nfc(toc_titles[href]).strip()
    guide_title = guide.get(href, {}).get("title")
    if guide_title:
        return nfc(guide_title).strip()
    for selector in ["h1", "h2", "h3", "title"]:
        node = soup.find(selector)
        if node:
            text = nfc(node.get_text(" ", strip=True)).strip()
            if text:
                return text
    if metadata_title:
        return metadata_title
    return None


def toc_override_for_document(href: str, role: str, included_docs: set[str]) -> bool | None:
    default = role != "frontmatter"
    actual = href in included_docs
    return None if actual == default else actual


def gather_body_root(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    body = soup.find("body")
    if body is None:
        return soup
    sections = [child for child in body.find_all(recursive=False) if isinstance(child, Tag)]
    if len(sections) == 1 and sections[0].name in {"section", "article", "div"}:
        return sections[0]
    return body


def safe_output_slug(base: str, seen: Counter[str]) -> str:
    seen[base] += 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def extract_cover_and_assets(
    zip_file: zipfile.ZipFile,
    manifest_order: list[dict],
    manifest: dict[str, dict],
    cover_href: str | None,
    output_dir: Path,
) -> tuple[dict[str, str], str | None]:
    image_map: dict[str, str] = {}
    cover_output: str | None = None
    image_seen: Counter[str] = Counter()

    for item in manifest_order:
        href = item["href"]
        media_type = item["media_type"]
        if not media_type.startswith("image/"):
            continue
        name = PurePosixPath(href).name
        target_name = safe_output_slug(name, image_seen)
        if href == cover_href:
            cover_output = f"cover{Path(name).suffix or '.jpg'}"
            (output_dir / cover_output).write_bytes(zip_file.read(href))
            image_map[href] = cover_output
            continue
        target_path = output_dir / "images" / target_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(zip_file.read(href))
        image_map[href] = f"images/{target_name}"
    return image_map, cover_output


def extract_css(zip_file: zipfile.ZipFile, manifest_order: list[dict], output_dir: Path) -> bool:
    css_items = [item for item in manifest_order if item["media_type"] == "text/css"]
    if not css_items:
        return False
    css_dir = output_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    pieces = []
    for item in css_items:
        pieces.append(zip_file.read(item["href"]).decode("utf-8", errors="replace"))
        pieces.append("\n\n")
    (css_dir / "style.css").write_text("".join(pieces), encoding="utf-8")
    return True


def rewrite_embedded_asset_hrefs(soup: BeautifulSoup, doc_href: str, image_map: dict[str, str]) -> None:
    base_dir = PurePosixPath(doc_href).parent.as_posix()
    for tag in soup.find_all(["img", "image"]):
        attr = "src" if tag.name == "img" else "href"
        href = tag.get(attr) or tag.get(f"{{{XLINK_NS}}}href")
        if not href:
            continue
        resolved = posixpath.normpath(posixpath.join(base_dir, href))
        if resolved in image_map:
            if tag.name == "img":
                tag["src"] = image_map[resolved]
            else:
                tag["href"] = image_map[resolved]
                if f"{{{XLINK_NS}}}href" in tag.attrs:
                    tag[f"{{{XLINK_NS}}}href"] = image_map[resolved]


class MarkdownRenderer:
    """XHTML → Markdown converter used by :func:`deconstruct`.

    Walks a parsed BeautifulSoup tree (the body of an EPUB chapter
    document) and emits clean Markdown — the kind an author would
    actually want to edit. **Best-effort**, with documented normalization:
    we don't try to round-trip every XHTML quirk; instead we choose the
    Markdown form that's closest to what a person would have typed in
    the first place.

    Behavior worth knowing about:

    - Headings, lists, blockquotes, code blocks, emphasis/strong, and
      links are all faithfully converted.
    - Tables are converted to GFM-style pipe tables.
    - Images are converted to ``![alt](href)``; figure captions become
      a paragraph below the image.
    - Footnotes use the ``[^id]`` Markdown extension format.
    - Inline styles, classes, and ``epub:type`` attributes are dropped
      unless they map to specific Markdown features.
    - Cross-document links are rewritten via :attr:`doc_href_to_md` so
      they point at the deconstructed Markdown chapter, not the
      original XHTML.

    :param doc_href_to_md: Map from EPUB document hrefs (as referenced
        in the source XHTML) to the corresponding output Markdown
        filenames. Used for rewriting cross-chapter links during
        rendering.
    """

    def __init__(self, doc_href_to_md: dict[str, str]):
        self.doc_href_to_md = doc_href_to_md
        self.current_doc_href = ""

    def render_document(self, root: Tag | BeautifulSoup, current_doc_href: str) -> str:
        """Convert one EPUB chapter's XHTML body to Markdown.

        :param root: The parsed body element (or document) of the source
            XHTML.
        :param current_doc_href: The EPUB-internal href of this document
            (used for resolving relative links).
        :returns: Markdown text with blank lines between blocks, no
            leading/trailing whitespace.
        """
        self.current_doc_href = current_doc_href
        blocks = self.render_blocks(list(root.children), 0)
        return "\n\n".join(block for block in blocks if block.strip()).strip()

    def render_blocks(self, nodes: list, depth: int) -> list[str]:
        blocks: list[str] = []
        for node in nodes:
            if isinstance(node, NavigableString):
                text = nfc(str(node)).strip()
                if text:
                    blocks.append(text)
                continue
            if not isinstance(node, Tag):
                continue
            name = node.name.lower()
            if name in {"script", "style", "nav"}:
                continue
            if name in {"body", "section", "article", "header", "footer", "main", "div"}:
                blocks.extend(self.render_blocks(list(node.children), depth))
                continue
            if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                level = int(name[1])
                text = self.render_inline_children(node).strip()
                if text:
                    blocks.append(f"{'#' * level} {text}")
                continue
            if name == "p":
                text = self.render_inline_children(node).strip()
                if text:
                    blocks.append(text)
                continue
            if name == "blockquote":
                inner = "\n\n".join(self.render_blocks(list(node.children), depth + 1)).strip()
                if inner:
                    blocks.append("\n".join("> " + line if line else ">" for line in inner.splitlines()))
                continue
            if name in {"ul", "ol"}:
                blocks.append(self.render_list(node, depth))
                continue
            if name == "dl":
                blocks.append(self.render_definition_list(node))
                continue
            if name == "pre":
                code = node.get_text("", strip=False).rstrip("\n")
                code_tag = node.find("code")
                language = ""
                if code_tag:
                    for class_name in code_tag.get("class", []):
                        if class_name.startswith("language-"):
                            language = class_name.removeprefix("language-")
                            break
                fence = f"```{language}".rstrip()
                blocks.append(f"{fence}\n{code}\n```")
                continue
            if name == "hr":
                blocks.append("---")
                continue
            if name == "table":
                table_md = self.render_table(node)
                if table_md:
                    blocks.append(table_md)
                continue
            if name == "figure":
                figure_md = self.render_figure(node)
                if figure_md:
                    blocks.append(figure_md)
                continue
            if name == "img":
                blocks.append(self.render_image(node))
                continue
            if name == "aside" and ("footnote" in extract_epub_type(node) or node.get("role") == "doc-footnote"):
                continue
            fallback = self.render_inline_children(node).strip()
            if fallback:
                blocks.append(fallback)
        return blocks

    def render_list(self, node: Tag, depth: int) -> str:
        lines: list[str] = []
        ordered = node.name == "ol"
        for index, li in enumerate(node.find_all("li", recursive=False), start=1):
            prefix = f"{index}. " if ordered else "- "
            child_blocks = self.render_blocks([child for child in li.children], depth + 1)
            if not child_blocks:
                lines.append(prefix.rstrip())
                continue
            first, *rest = child_blocks
            lines.append(prefix + first)
            for block in rest:
                for block_line in block.splitlines():
                    lines.append("  " + block_line)
        return "\n".join(lines)

    def render_definition_list(self, node: Tag) -> str:
        lines: list[str] = []
        children = [child for child in node.children if isinstance(child, Tag)]
        for child in children:
            if child.name == "dt":
                lines.append(self.render_inline_children(child).strip())
            elif child.name == "dd":
                lines.append(f": {self.render_inline_children(child).strip()}")
        return "\n".join(lines)

    def render_table(self, node: Tag) -> str:
        rows = []
        for tr in node.find_all("tr"):
            cells = [self.render_inline_children(cell).strip() for cell in tr.find_all(["th", "td"], recursive=False)]
            if cells:
                rows.append(cells)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        padded = [row + [""] * (width - len(row)) for row in rows]
        header = padded[0]
        divider = ["---"] * width
        body = padded[1:] if len(padded) > 1 else []
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(divider) + " |"]
        lines.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(lines)

    def render_figure(self, node: Tag) -> str:
        img = node.find("img")
        if img is None:
            return self.render_inline_children(node).strip()
        caption = node.find("figcaption")
        return self.render_image(img, caption_text=self.render_inline_children(caption).strip() if caption else None)

    def render_image(self, node: Tag, caption_text: str | None = None) -> str:
        alt = node.get("alt", "")
        src = node.get("src") or ""
        if node.name == "image":
            src = node.get("href") or node.get(f"{{{XLINK_NS}}}href") or ""
        title = f' "{caption_text}"' if caption_text else ""
        return f"![{alt}]({src}{title})"

    def render_inline_children(self, node: Tag | None) -> str:
        if node is None:
            return ""
        parts: list[str] = []
        for child in node.children:
            rendered = self.render_inline(child)
            if parts and parts[-1].endswith("!") and rendered.startswith("["):
                # Avoid accidental image syntax (`![...]`) when punctuation precedes links.
                rendered = f" {rendered}"
            parts.append(rendered)
        return "".join(parts)

    def render_inline(self, node) -> str:
        if isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", nfc(str(node)))
            # Preserve literal bracket text from source documents (for example
            # Markdown syntax examples inside prose) instead of creating links.
            return text.replace("[", "\\[").replace("]", "\\]")
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if name in {"strong", "b"}:
            return f"**{self.render_inline_children(node)}**"
        if name in {"em", "i", "cite"}:
            return f"*{self.render_inline_children(node)}*"
        if name == "code":
            return f"`{node.get_text('', strip=False)}`"
        if name == "del":
            return f"~~{self.render_inline_children(node)}~~"
        if name == "br":
            return "<br />\n"
        if name == "a":
            href = node.get("href", "")
            text = self.render_inline_children(node) or href
            if "noteref" in extract_epub_type(node) or node.get("role") == "doc-noteref":
                label = href.split("#fn-", 1)[1] if "#fn-" in href else text
                return f"[^{label}]"
            rewritten = self.rewrite_href(href)
            if rewritten is None:
                return text
            if URLISH_RE.fullmatch(text) and text == rewritten:
                return f"<{rewritten}>"
            return f"[{text}]({rewritten})"
        if name == "img":
            return self.render_image(node)
        if name == "sup":
            return self.render_inline_children(node)
        if name == "sub":
            return self.render_inline_children(node)
        if name == "span" or name == "abbr" or name == "small" or name == "q":
            return self.render_inline_children(node)
        return self.render_inline_children(node)

    def rewrite_href(self, href: str) -> str | None:
        if not href:
            return href
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme not in {"mailto"}:
            return href
        if href.startswith("#"):
            return "#"
        base_dir = PurePosixPath(self.current_doc_href).parent.as_posix()
        path = posixpath.normpath(posixpath.join(base_dir, parsed.path))
        if path == self.current_doc_href:
            return "#"
        if path in self.doc_href_to_md:
            return self.doc_href_to_md[path]
        if parsed.path.endswith((".xhtml", ".html", ".md")):
            return None
        return href


def collect_footnotes(soup: BeautifulSoup) -> list[tuple[str, str]]:
    collected = []
    for aside in list(soup.find_all("aside")):
        if "footnote" not in extract_epub_type(aside) and aside.get("role") != "doc-footnote":
            continue
        note_id = aside.get("id", "")
        label = note_id.removeprefix("fn-") or str(len(collected) + 1)
        inner = []
        for child in aside.children:
            if isinstance(child, Tag):
                inner.append(child)
        renderer = MarkdownRenderer({})
        content = "\n\n".join(renderer.render_blocks(inner, 0)).strip()
        content = re.sub(r"^\[[^\]]+]\([^)]+\)\s*", "", content)
        collected.append((label, content))
        aside.decompose()
    return collected


def serialize_frontmatter(meta: dict) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip() + "\n---\n"


def deconstruct(epub_path: str, output_dir: str | None = None) -> bool:
    """Convert an EPUB back to a ProseDown project on disk.

    Best-effort EPUB → Markdown. The goal is **readable Markdown an
    author would want to edit**, not a lossless archive of the original
    EPUB. Some XHTML artifacts deliberately don't survive because
    representing them in Markdown would make the source file
    unreadable (inline ``style`` attributes, custom CSS classes,
    decorative ``<span>`` wrappers).

    Pipeline:

    1. Open the EPUB as a ZIP, locate ``META-INF/container.xml`` to find
       the OPF.
    2. Read OPF metadata: title, authors, language, identifier.
    3. Read the spine, the navigation document, and any NCX.
    4. For each spine document, classify by role
       (cover / titlepage / chapter / glossary / etc.).
    5. Extract images, fonts, and CSS into ``css/`` and ``images/``
       under the output directory.
    6. Convert each chapter's XHTML body to Markdown via
       :class:`MarkdownRenderer`.
    7. Write ``book.md`` with the project frontmatter and one ``.md``
       file per chapter, numbered to preserve spine order.

    :param epub_path: Path to a ``.epub`` file.
    :param output_dir: Directory to populate with the deconstructed
        project. Created if it doesn't exist. Defaults to a folder
        named after the book's title in the EPUB's parent directory.
    :returns: ``True`` if deconstruction completed without errors.
        Warnings (lossy conversions, unrecognized features) don't
        cause a ``False`` return — they're reported on stdout.
    """
    diagnostics = DiagnosticBag()
    epub_file = Path(epub_path).expanduser().resolve()
    if not epub_file.exists():
        diagnostics.error("EPUB file not found", epub_file)
        diagnostics.emit()
        return False
    out_dir = Path(output_dir).expanduser() if output_dir else Path(epub_file.stem)
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(epub_file) as zf:
        if "META-INF/encryption.xml" in zf.namelist():
            diagnostics.error("DRM-encrypted EPUBs are outside ProseDown's scope", epub_file)
            diagnostics.emit()
            return False
        opf_path = epub_rootfile(zf)
        opf_root = parse_xml(zf.read(opf_path))
        manifest, manifest_order, _by_href = manifest_items(opf_root, opf_path)
        spine_hrefs = spine_document_hrefs(opf_root, manifest)
        guide = parse_guide(opf_root, opf_path)

        package_meta = parse_epub_metadata(opf_root)
        package_title = package_meta.get("title")
        if not normalize_author_list(package_meta.get("author")):
            package_meta["author"] = "Unknown"
            diagnostics.warn("Source EPUB missing dc:creator; using author: Unknown", epub_file)

        nav_href = next((item["href"] for item in manifest_order if "nav" in item["properties"]), None)
        toc_titles: dict[str, str] = {}
        included_docs: set[str] = set()
        toc_part_docs: set[str] = set()
        if nav_href and nav_href in zf.namelist():
            toc_titles, included_docs, toc_part_docs = parse_nav_document(zf, nav_href)
        else:
            ncx_entry = next((item["href"] for item in manifest_order if item["media_type"] == "application/x-dtbncx+xml"), None)
            if ncx_entry and ncx_entry in zf.namelist():
                toc_titles = parse_ncx(zf, ncx_entry)
                included_docs = set(toc_titles)

        cover_href = cover_href_from_opf(opf_root, manifest)
        image_map, cover_output = extract_cover_and_assets(zf, manifest_order, manifest, cover_href, out_dir)
        extract_css(zf, manifest_order, out_dir)

        documents: list[ParsedEpubDocument] = []
        for index, href in enumerate(spine_hrefs):
            if href not in zf.namelist():
                continue
            soup = BeautifulSoup(zf.read(href), "html.parser")
            rewrite_embedded_asset_hrefs(soup, href, image_map)
            role, source_slug = detect_role_from_document(href, soup, guide, toc_part_docs)
            title = detect_title_from_document(href, soup, toc_titles, guide, package_title)
            toc_override = toc_override_for_document(href, role, included_docs)
            documents.append(
                ParsedEpubDocument(
                    spine_index=index,
                    href=href,
                    title=title,
                    role=role,
                    toc_override=toc_override,
                    source_slug=source_slug,
                    soup=soup,
                    body_root=gather_body_root(soup),
                )
            )

        padding = max(2, len(str(max(1, len(documents)))))
        seen_slugs: Counter[str] = Counter()
        href_to_md: dict[str, str] = {}
        planned_docs: list[tuple[ParsedEpubDocument, str, str]] = []
        for document in documents:
            canonical_role_slug = document.source_slug in (
                FRONTMATTER_SLUGS
                | BACKMATTER_SLUGS
                | {"epilogue", "titlepage", "halftitlepage", "table-of-contents", "toc", "endnotes"}
            )
            title_slug = document.source_slug if canonical_role_slug else (slugify(document.title) if document.title else document.source_slug)
            output_slug = safe_output_slug(title_slug, seen_slugs)
            filename = f"{document.spine_index:0{padding}d}-{output_slug}.md"
            href_to_md[document.href] = filename
            planned_docs.append((document, output_slug, filename))

        renderer = MarkdownRenderer(href_to_md)
        for document, output_slug, filename in planned_docs:
            body_soup = BeautifulSoup(str(document.body_root), "html.parser")
            footnotes = collect_footnotes(body_soup)
            markdown_body = renderer.render_document(body_soup, document.href)
            if footnotes:
                footnote_lines = [markdown_body.strip()] if markdown_body.strip() else []
                for label, content in footnotes:
                    footnote_lines.append(f"[^{label}]: {content}".strip())
                markdown_body = "\n\n".join(part for part in footnote_lines if part)

            chapter_meta = {
                "title": document.title or deslugify(output_slug),
                "role": document.role,
            }
            if document.toc_override is not None:
                chapter_meta["toc"] = document.toc_override

            content = serialize_frontmatter(chapter_meta)
            if markdown_body.strip():
                content += markdown_body.strip() + "\n"
            (out_dir / filename).write_text(content, encoding="utf-8")

        book_md = package_meta.copy()
        if "language" not in book_md:
            book_md["language"] = "en"
        if cover_output:
            book_md["cover"] = cover_output
        if (out_dir / "css" / "style.css").exists():
            book_md["css"] = "css/style.css"
        (out_dir / "book.md").write_text(serialize_frontmatter(book_md), encoding="utf-8")

    diagnostics.emit()
    return not diagnostics.has_errors


def main() -> None:
    """Console-script entry point.

    Wired up as ``prosedown`` via ``[project.scripts]`` in pyproject.toml.
    Dispatches to :func:`build` or :func:`deconstruct` depending on the
    subcommand. Exits with status 0 on success, 1 on any diagnostic error.
    """
    parser = argparse.ArgumentParser(
        prog="prosedown",
        description="ProseDown CLI — Markdown ↔ EPUB compiler and deconstructor.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"prosedown {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="ProseDown → EPUB")
    build_parser.add_argument("input", help="Path to a single .md file or project directory")
    build_parser.add_argument("--output", "-o", help="Output EPUB path")

    deconstruct_parser = subparsers.add_parser("deconstruct", help="EPUB → ProseDown")
    deconstruct_parser.add_argument("input", help="Path to an EPUB file")
    deconstruct_parser.add_argument("--output", "-o", help="Output directory")

    args = parser.parse_args()
    if args.command == "build":
        ok = build(args.input, args.output)
    elif args.command == "deconstruct":
        ok = deconstruct(args.input, args.output)
    else:
        parser.print_help()
        sys.exit(1)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
