#!/usr/bin/env python3
"""
ProseDown CLI test suite

Usage:
    source cli/.venv/bin/activate
    python cli/test_suite.py
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import sys
import time
import traceback
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

# Allow running this script directly (`python tests/test_suite.py`) without
# requiring an `pip install -e .` first, by injecting the src/ tree onto path.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from prosedown import (  # noqa: E402
    MarkdownRenderer,
    build,
    canonical_uuid_input,
    deconstruct,
    deterministic_uuid,
    parse_frontmatter,
    slugify,
    smartypants_segment,
    title_resolution,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_OUTPUT = PROJECT_ROOT / "build" / "test-output"
REPORT_PATH = TEST_OUTPUT / "test-results.json"

# The synthetic example projects ship in this repo and are always available.
# They drive the build / round-trip tests on every push.
EXAMPLE_SINGLE = PROJECT_ROOT / "spec" / "examples" / "single-file" / "my-essay.md"
EXAMPLE_MULTI = PROJECT_ROOT / "spec" / "examples" / "multi-chapter"

# The corpus tests run against real-world EPUBs (Standard Ebooks, Project
# Gutenberg, Google Docs exports, commercial samples). The corpus is large
# (200+ MB) and can include copyrighted material that we don't redistribute,
# so it isn't checked into this repo. Maintainers point at a local corpus by
# setting PROSEDOWN_CORPUS=/path/to/corpus, where the directory layout is:
#
#   <corpus>/epub-standardebooks/*.epub
#   <corpus>/epub-drm-free/*.epub
#   <corpus>/google-docs-epub/*.epub
#   <corpus>/gutenberg-project/pg1342.epub
#
# When the env var isn't set or the path doesn't exist, all corpus tests
# are skipped and CI still passes against the synthetic fixtures.
import os

CORPUS_ROOT = Path(os.environ.get("PROSEDOWN_CORPUS", str(PROJECT_ROOT / "spec" / "source")))
HAS_CORPUS = CORPUS_ROOT.exists() and CORPUS_ROOT.is_dir()


def _corpus_glob(subdir: str, pattern: str = "*.epub") -> list[Path]:
    target = CORPUS_ROOT / subdir
    if not HAS_CORPUS or not target.exists():
        return []
    return sorted(target.glob(pattern))


def _corpus_file(*parts: str) -> Path | None:
    candidate = CORPUS_ROOT.joinpath(*parts)
    return candidate if HAS_CORPUS and candidate.exists() else None


STANDARD_EPUBS = _corpus_glob("epub-standardebooks")
COMMERCIAL_EPUBS = _corpus_glob("epub-drm-free")
GOOGLE_DOCS_EPUB = _corpus_file("google-docs-epub", "ProseDown Spec Review and Improvement.epub")
GUTENBERG_PG1342 = _corpus_file("gutenberg-project", "pg1342.epub")

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+rH9sAAAAASUVORK5CYII="
)


@dataclass
class Invocation:
    ok: bool
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


@dataclass
class TestResult:
    name: str
    category: str
    passed: bool = False
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
        }


def invoke(func, *args) -> Invocation:
    stdout = io.StringIO()
    stderr = io.StringIO()
    start = time.perf_counter()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        ok = func(*args)
    duration_ms = int((time.perf_counter() - start) * 1000)
    return Invocation(ok=ok, stdout=stdout.getvalue(), stderr=stderr.getvalue(), duration_ms=duration_ms)


def fresh_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_files(root: Path, files: dict[str, str | bytes]) -> None:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")


def read_zip_text(zip_path: Path, member: str) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(member).decode("utf-8")


def epub_structure_ok(zip_path: Path) -> tuple[bool, list[str]]:
    issues = []
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        if not infos:
            return False, ["Archive is empty"]
        if infos[0].filename != "mimetype":
            issues.append("mimetype is not the first ZIP entry")
        if infos[0].compress_type != zipfile.ZIP_STORED:
            issues.append("mimetype entry is compressed")
    return len(issues) == 0, issues


def snapshot_tree(root: Path) -> dict[str, str]:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() in {".md", ".css"}:
            snapshot[rel] = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        else:
            snapshot[rel] = f"<bin:{path.stat().st_size}>"
    return snapshot


def diff_snapshots(first: dict[str, str], second: dict[str, str]) -> list[str]:
    diffs = []
    for key in sorted(set(first) | set(second)):
        if key not in first:
            diffs.append(f"added:{key}")
        elif key not in second:
            diffs.append(f"removed:{key}")
        elif first[key] != second[key]:
            diffs.append(f"changed:{key}")
    return diffs


def find_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*.md") if path.name != "book.md")


def expect(condition: bool, result: TestResult, message: str) -> None:
    if not condition:
        result.errors.append(message)


def run_algorithm_tests() -> list[TestResult]:
    results = []

    result = TestResult("slug-generation", "unit")
    start = time.perf_counter()
    try:
        expect(slugify("The Mountain Trail") == "the-mountain-trail", result, "basic slug generation failed")
        expect(slugify("Cafe\u0301 au_lait!") == "café-au-lait", result, "NFC/underscore normalization failed")
        expect(slugify("___") == "section", result, "empty slug fallback failed")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    result = TestResult("title-resolution", "unit")
    start = time.perf_counter()
    try:
        expect(title_resolution("Frontmatter", "Heading", "chapter-name") == "Frontmatter", result, "frontmatter title should win")
        expect(title_resolution(None, "Heading", "chapter-name") == "Heading", result, "first heading should be second precedence")
        expect(title_resolution(None, None, "the-summit") == "The Summit", result, "filename fallback should de-slugify")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    result = TestResult("uuid-serialization", "unit")
    start = time.perf_counter()
    try:
        expected_input = "The Mountain Trail|Jeff Alldridge|en"
        expected_uuid = "ff4e2f77-46bf-5ee7-8156-2c7437b16b65"
        expect(canonical_uuid_input("The Mountain Trail", ["Jeff Alldridge"], "en") == expected_input, result, "UUID input serialization mismatch")
        expect(deterministic_uuid("The Mountain Trail", ["Jeff Alldridge"], "en") == expected_uuid, result, "deterministic UUID mismatch")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    result = TestResult("frontmatter-parsing", "unit")
    start = time.perf_counter()
    try:
        workspace = fresh_dir(TEST_OUTPUT / "unit-frontmatter")
        path = workspace / "sample.md"
        path.write_text("---\ntitle: Sample\nauthor: Tester\n---\n\n# Sample\n", encoding="utf-8")
        meta, body = parse_frontmatter(path)
        expect(meta is not None and meta.get("title") == "Sample", result, "parse_frontmatter lost title")
        expect(body is not None and body.strip().startswith("# Sample"), result, "parse_frontmatter lost body")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    result = TestResult("smart-typography-primes", "unit")
    start = time.perf_counter()
    try:
        transformed, supported = smartypants_segment("Height: 5' 10\"", "en")
        expect("5′ 10″" in transformed, result, "feet/inches prime conversion failed")
        expect(supported, result, "english quote style should be supported")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    result = TestResult("deconstruct-link-normalization", "unit")
    start = time.perf_counter()
    try:
        renderer = MarkdownRenderer({"OPS/chapter-2.xhtml": "02-chapter-2.md"})
        renderer.current_doc_href = "OPS/chapter-1.xhtml"
        expect(
            renderer.rewrite_href("chapter-2.xhtml#CHAPTER_II") == "02-chapter-2.md",
            result,
            "non-canonical fragments should be dropped during rewrite",
        )
        expect(
            renderer.rewrite_href("chapter-2.xhtml#chapter-ii") == "02-chapter-2.md",
            result,
            "fragments are intentionally normalized out during rewrite",
        )
        sample = BeautifulSoup('<p>Love!<a href="#foot_note">7</a></p>', "html.parser")
        rendered = renderer.render_inline_children(sample.p)
        expect("Love! [7](#)" in rendered, result, "link rendering should avoid accidental image syntax")
        result.passed = not result.errors
    except Exception as exc:  # pragma: no cover
        result.errors.append(str(exc))
    result.duration_ms = int((time.perf_counter() - start) * 1000)
    results.append(result)

    return results


def regression_build_case(name: str, files: dict[str, str | bytes], expect_ok: bool, expected_text: str | None = None, output_epub: str = "out.epub") -> TestResult:
    result = TestResult(name, "regression")
    workspace = fresh_dir(TEST_OUTPUT / "regression" / name)
    write_files(workspace, files)
    invocation = invoke(build, str(workspace), str(workspace / output_epub))
    result.duration_ms = invocation.duration_ms
    result.stats["ok"] = invocation.ok
    if expect_ok:
        expect(invocation.ok, result, "build() should have succeeded")
    else:
        expect(not invocation.ok, result, "build() should have failed")
    if expected_text:
        expect(expected_text in invocation.output, result, f"expected diagnostic containing: {expected_text}")
    if invocation.ok and (workspace / output_epub).exists():
        ok_structure, issues = epub_structure_ok(workspace / output_epub)
        if not ok_structure:
            result.errors.extend(issues)
    result.passed = not result.errors
    return result


def run_regression_tests() -> list[TestResult]:
    results = []

    results.append(
        regression_build_case(
            "missing-title",
            {
                "book.md": "---\nauthor: Tester\n---\n",
                "01-chapter.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Missing title or author",
        )
    )

    results.append(
        regression_build_case(
            "missing-author",
            {
                "book.md": "---\ntitle: Missing Author\n---\n",
                "01-chapter.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Missing title or author",
        )
    )

    results.append(
        regression_build_case(
            "malformed-yaml",
            {
                "book.md": "---\ntitle: [oops\n---\n",
                "01-chapter.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Malformed YAML frontmatter",
        )
    )

    results.append(
        regression_build_case(
            "duplicate-prefix",
            {
                "book.md": "---\ntitle: Duplicate Prefix\nauthor: Tester\n---\n",
                "01-one.md": "# One\n",
                "1-two.md": "# Two\n",
            },
            expect_ok=False,
            expected_text="Duplicate numeric prefixes are ambiguous",
        )
    )

    results.append(
        regression_build_case(
            "missing-chapters-entry",
            {
                "book.md": "---\ntitle: Missing File\nauthor: Tester\nchapters:\n  - 01-one.md\n  - missing.md\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=False,
            expected_text="doesn't exist",
        )
    )

    results.append(
        regression_build_case(
            "duplicate-chapters-entry",
            {
                "book.md": "---\ntitle: Duplicate Chapter\nauthor: Tester\nchapters:\n  - 01-one.md\n  - 01-one.md\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Duplicate entry in chapters:",
        )
    )

    results.append(
        regression_build_case(
            "book-md-in-chapters",
            {
                "book.md": "---\ntitle: Bad Chapters\nauthor: Tester\nchapters:\n  - book.md\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=False,
            expected_text="book.md MUST NOT appear in chapters:",
        )
    )

    results.append(
        regression_build_case(
            "remote-image-url",
            {
                "book.md": "---\ntitle: Remote Image\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n![Bad](https://example.com/pic.png)\n",
            },
            expect_ok=False,
            expected_text="Remote image URL in Markdown",
        )
    )

    results.append(
        regression_build_case(
            "broken-internal-link",
            {
                "book.md": "---\ntitle: Broken Link\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n[Missing](02-two.md#nope)\n",
            },
            expect_ok=False,
            expected_text="Broken internal links MUST produce an error",
        )
    )

    results.append(
        regression_build_case(
            "path-traversal",
            {
                "book.md": "---\ntitle: Traversal\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n![Bad](../outside.png)\n",
            },
            expect_ok=False,
            expected_text="Path traversal (`..` segments) is forbidden",
        )
    )

    result = TestResult("invalid-utf8", "regression")
    workspace = fresh_dir(TEST_OUTPUT / "regression" / "invalid-utf8")
    write_files(
        workspace,
        {
            "book.md": "---\ntitle: Invalid UTF8\nauthor: Tester\n---\n",
            "01-one.md": b"\xff\xfe\xfd",
        },
    )
    invocation = invoke(build, str(workspace), str(workspace / "out.epub"))
    result.duration_ms = invocation.duration_ms
    expect(not invocation.ok, result, "build() should fail on invalid UTF-8")
    expect("Invalid UTF-8 in source files" in invocation.output, result, "missing invalid UTF-8 diagnostic")
    result.passed = not result.errors
    results.append(result)

    result = TestResult("nul-bytes", "regression")
    workspace = fresh_dir(TEST_OUTPUT / "regression" / "nul-bytes")
    write_files(
        workspace,
        {
            "book.md": "---\ntitle: NUL Bytes\nauthor: Tester\n---\n",
            "01-one.md": b"# One\n\x00\n",
        },
    )
    invocation = invoke(build, str(workspace), str(workspace / "out.epub"))
    result.duration_ms = invocation.duration_ms
    expect(not invocation.ok, result, "build() should fail on NUL bytes")
    expect("NUL bytes in source files MUST produce an error" in invocation.output, result, "missing NUL-byte diagnostic")
    result.passed = not result.errors
    results.append(result)

    results.append(
        regression_build_case(
            "empty-title",
            {
                "book.md": "---\ntitle: ''\nauthor: Tester\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Missing title or author",
        )
    )

    results.append(
        regression_build_case(
            "empty-author-list",
            {
                "book.md": "---\ntitle: Empty Author\nauthor: []\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=False,
            expected_text="Missing title or author",
        )
    )

    results.append(
        regression_build_case(
            "chapters-empty-list-falls-back",
            {
                "book.md": "---\ntitle: Fallback\nauthor: Tester\nchapters: []\n---\n",
                "01-one.md": "# One\n",
            },
            expect_ok=True,
        )
    )

    results.append(
        regression_build_case(
            "warning-no-heading",
            {
                "book.md": "---\ntitle: No Heading\nauthor: Tester\n---\n",
                "01-one.md": "Plain body paragraph.\n",
            },
            expect_ok=True,
            expected_text="Title derived from filename",
        )
    )

    results.append(
        regression_build_case(
            "warning-unprefixed-md",
            {
                "book.md": "---\ntitle: Unprefixed\nauthor: Tester\n---\n",
                "01-one.md": "# One\n",
                "notes.md": "# Notes\n",
            },
            expect_ok=True,
            expected_text="File not included — add numeric prefix or list in chapters:",
        )
    )

    results.append(
        regression_build_case(
            "warning-title-mismatch",
            {
                "book.md": "---\ntitle: Title Mismatch\nauthor: Tester\n---\n",
                "01-one.md": "---\ntitle: TOC Title\n---\n# Rendered Heading\n",
            },
            expect_ok=True,
            expected_text="TOC uses frontmatter title; heading renders in body",
        )
    )

    results.append(
        regression_build_case(
            "warning-cover-size",
            {
                "book.md": "---\ntitle: Tiny Cover\nauthor: Tester\n---\n",
                "01-one.md": "# One\n",
                "cover.png": PNG_1X1,
            },
            expect_ok=True,
            expected_text="Recommended minimum 1600×2560 for retail",
        )
    )

    results.append(
        regression_build_case(
            "warning-skipped-heading-level",
            {
                "book.md": "---\ntitle: Heading Levels\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n### Three\n",
            },
            expect_ok=True,
            expected_text="Heading jumps from H1 to H3",
        )
    )

    results.append(
        regression_build_case(
            "warning-unsupported-language",
            {
                "book.md": "---\ntitle: Esperanto Book\nauthor: Tester\nlanguage: eo\n---\n",
                "01-one.md": "# One\n\n\"Quoted text\"\n",
            },
            expect_ok=True,
            expected_text="Falling back to English-style quotes",
        )
    )

    results.append(
        regression_build_case(
            "warning-unpadded-prefix",
            {
                "book.md": "---\ntitle: Unpadded\nauthor: Tester\n---\n",
                "1-one.md": "# One\n",
            },
            expect_ok=True,
            expected_text="Consider zero-padding: 01- instead of 1-",
        )
    )

    results.append(
        regression_build_case(
            "warning-multiple-h1",
            {
                "book.md": "---\ntitle: Multiple H1\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n# Two\n",
            },
            expect_ok=True,
            expected_text="Only the first H1 is used",
        )
    )

    results.append(
        regression_build_case(
            "warning-missing-alt",
            {
                "book.md": "---\ntitle: Alt Warning\nauthor: Tester\n---\n",
                "01-one.md": "# One\n\n<img src=\"images/pic.png\" />\n",
                "images/pic.png": PNG_1X1,
            },
            expect_ok=True,
            expected_text="Missing alt text affects accessibility",
        )
    )

    result = TestResult("chapter-language-override-and-primes", "regression")
    workspace = fresh_dir(TEST_OUTPUT / "regression" / "chapter-language-override-and-primes")
    write_files(
        workspace,
        {
            "book.md": "---\ntitle: Language Overrides\nauthor: Tester\nlanguage: en\n---\n",
            "01-english.md": "# English\n\n\"quoted\"\n",
            "02-french.md": "---\nlanguage: fr\n---\n# French\n\n\"bonjour\"\n\n5' 10\"\n",
        },
    )
    invocation = invoke(build, str(workspace), str(workspace / "out.epub"))
    result.duration_ms = invocation.duration_ms
    expect(invocation.ok, result, "build() should succeed with chapter language overrides")
    if invocation.ok and (workspace / "out.epub").exists():
        english = read_zip_text(workspace / "out.epub", "EPUB/text/english.xhtml")
        french = read_zip_text(workspace / "out.epub", "EPUB/text/french.xhtml")
        expect('xml:lang="en"' in english, result, "book language should apply to default chapter documents")
        expect('xml:lang="fr"' in french, result, "chapter language override should set xml:lang")
        expect("«" in french and "»" in french, result, "chapter language override should drive quote style")
        expect("5′ 10″" in french, result, "feet/inches should convert to prime and double-prime")
    result.passed = not result.errors
    results.append(result)

    result = TestResult("deconstruct-padding-width-100-docs", "regression")
    workspace = fresh_dir(TEST_OUTPUT / "regression" / "deconstruct-padding-width-100-docs")
    source = workspace / "source"
    source.mkdir(parents=True, exist_ok=True)
    write_files(
        source,
        {
            "book.md": "---\ntitle: Padding Test\nauthor: Tester\n---\n",
            **{f"{index:03d}-chapter-{index}.md": f"# Chapter {index}\n\nBody.\n" for index in range(1, 101)},
        },
    )
    build_invocation = invoke(build, str(source), str(workspace / "source.epub"))
    decon_invocation = invoke(
        deconstruct,
        str(workspace / "source.epub"),
        str(workspace / "deconstructed"),
    ) if build_invocation.ok else Invocation(False, "", "", 0)
    result.duration_ms = build_invocation.duration_ms + decon_invocation.duration_ms
    expect(build_invocation.ok, result, "seed build should succeed")
    expect(decon_invocation.ok, result, "deconstruct() should succeed for 100-document EPUB")
    if decon_invocation.ok:
        chapter_files = sorted(path.name for path in find_markdown_files(workspace / "deconstructed"))
        expect(len(chapter_files) == 100, result, "expected 100 deconstructed chapter files")
        expect(chapter_files[0].startswith("000-"), result, "first chapter should use 3-digit padding")
        expect(chapter_files[-1].startswith("099-"), result, "last chapter should use 3-digit padding")
    result.passed = not result.errors
    results.append(result)

    if GOOGLE_DOCS_EPUB is not None:
        result = TestResult("google-docs-roundtrip-buildable", "regression")
        workspace = fresh_dir(TEST_OUTPUT / "regression" / "google-docs-roundtrip-buildable")
        first_dir = workspace / "first"
        invocation_deconstruct = invoke(deconstruct, str(GOOGLE_DOCS_EPUB), str(first_dir))
        invocation_build = invoke(build, str(first_dir), str(workspace / "rebuilt.epub")) if invocation_deconstruct.ok else Invocation(False, "", "", 0)
        result.duration_ms = invocation_deconstruct.duration_ms + invocation_build.duration_ms
        expect(invocation_deconstruct.ok, result, "deconstruct() should succeed for Google Docs fixture")
        expect(invocation_build.ok, result, "build() should succeed after deconstructing Google Docs fixture")
        if first_dir.exists() and (first_dir / "book.md").exists():
            meta, _body = parse_frontmatter(first_dir / "book.md")
            expect(meta is not None and bool(meta.get("author")), result, "deconstruction should emit buildable author metadata")
        result.passed = not result.errors
        results.append(result)

    if GUTENBERG_PG1342 is not None:
        result = TestResult("gutenberg-pg1342-roundtrip-buildable", "regression")
        workspace = fresh_dir(TEST_OUTPUT / "regression" / "gutenberg-pg1342-roundtrip-buildable")
        first_dir = workspace / "first"
        invocation_deconstruct = invoke(deconstruct, str(GUTENBERG_PG1342), str(first_dir))
        invocation_build = invoke(build, str(first_dir), str(workspace / "rebuilt.epub")) if invocation_deconstruct.ok else Invocation(False, "", "", 0)
        result.duration_ms = invocation_deconstruct.duration_ms + invocation_build.duration_ms
        expect(invocation_deconstruct.ok, result, "deconstruct() should succeed for Gutenberg pg1342")
        expect(invocation_build.ok, result, "build() should succeed after deconstructing Gutenberg pg1342")
        result.passed = not result.errors
        results.append(result)

    return results


def run_build_example_test(name: str, source: Path) -> TestResult:
    result = TestResult(name, "build-example")
    output_epub = TEST_OUTPUT / "examples" / f"{name}.epub"
    output_epub.parent.mkdir(parents=True, exist_ok=True)
    invocation = invoke(build, str(source), str(output_epub))
    result.duration_ms = invocation.duration_ms
    expect(invocation.ok, result, "build() failed")
    expect(output_epub.exists(), result, "expected EPUB was not written")
    if output_epub.exists():
        ok_structure, issues = epub_structure_ok(output_epub)
        if not ok_structure:
            result.errors.extend(issues)
        opf = read_zip_text(output_epub, "EPUB/content.opf")
        result.stats["epub_size_kb"] = output_epub.stat().st_size // 1024
        expect("property=\"dcterms:modified\"" in opf, result, "missing dcterms:modified")
        expect("toc.ncx" in opf, result, "missing toc.ncx manifest entry")
    result.passed = not result.errors
    return result


def run_example_roundtrip_test(name: str, source: Path) -> TestResult:
    result = TestResult(name, "example-roundtrip")
    work = fresh_dir(TEST_OUTPUT / "example-roundtrip" / name)
    first_dir = work / "first"
    second_dir = work / "second"
    first_epub = work / "original.epub"
    rebuilt_epub = work / "rebuilt.epub"

    start = time.perf_counter()
    try:
        first_build = invoke(build, str(source), str(first_epub))
        first_decon = invoke(deconstruct, str(first_epub), str(first_dir))
        rebuild = invoke(build, str(first_dir), str(rebuilt_epub))
        second_decon = invoke(deconstruct, str(rebuilt_epub), str(second_dir))
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        expect(first_build.ok and first_decon.ok and rebuild.ok and second_decon.ok, result, "example round-trip pipeline failed")
        if first_decon.ok and second_decon.ok:
            diffs = diff_snapshots(snapshot_tree(first_dir), snapshot_tree(second_dir))
            result.stats["drift_count"] = len(diffs)
            if diffs:
                result.warnings.append("; ".join(diffs[:8]))
            expect(len(diffs) == 0, result, "example round-trip drift should be zero")
    except Exception as exc:  # pragma: no cover
        result.errors.append(f"Exception: {exc}")
        result.errors.append(traceback.format_exc())
    result.passed = not result.errors
    return result


def chapter_stats(project_dir: Path) -> dict:
    md_files = find_markdown_files(project_dir)
    book_md = project_dir / "book.md"
    meta, _body = parse_frontmatter(book_md)
    return {
        "chapters": len(md_files),
        "metadata_fields": len(meta or {}),
        "has_cover": any(project_dir.glob("cover.*")),
        "has_css": (project_dir / "css" / "style.css").exists(),
        "images": len(list((project_dir / "images").glob("*"))) if (project_dir / "images").exists() else 0,
    }


def run_deconstruct_fixture_test(epub_path: Path, category: str) -> TestResult:
    result = TestResult(epub_path.name, category)
    output_dir = fresh_dir(TEST_OUTPUT / category / epub_path.stem)
    invocation = invoke(deconstruct, str(epub_path), str(output_dir))
    result.duration_ms = invocation.duration_ms
    expect(invocation.ok, result, "deconstruct() failed")
    expect((output_dir / "book.md").exists(), result, "book.md was not generated")
    if (output_dir / "book.md").exists():
        meta, _body = parse_frontmatter(output_dir / "book.md")
        expect(meta is not None and bool(meta.get("title")), result, "book.md missing title")
        expect(meta is not None and bool(meta.get("author")), result, "book.md missing author")
    md_files = find_markdown_files(output_dir)
    expect(bool(md_files), result, "no chapter markdown files were generated")
    if md_files:
        first_meta, _body = parse_frontmatter(md_files[0])
        expect(first_meta is not None and "title" in first_meta and "role" in first_meta, result, "chapter frontmatter missing explicit title/role")
    result.stats.update(chapter_stats(output_dir))
    result.passed = not result.errors
    return result


def run_standard_roundtrip_test(epub_path: Path) -> TestResult:
    result = TestResult(epub_path.name, "standard-roundtrip")
    work = fresh_dir(TEST_OUTPUT / "standard-roundtrip" / epub_path.stem)
    first_dir = work / "first"
    second_dir = work / "second"
    rebuilt_epub = work / "rebuilt.epub"
    start = time.perf_counter()
    try:
        first = invoke(deconstruct, str(epub_path), str(first_dir))
        rebuilt = invoke(build, str(first_dir), str(rebuilt_epub)) if first.ok else Invocation(False, "", "", 0)
        second = invoke(deconstruct, str(rebuilt_epub), str(second_dir)) if rebuilt.ok else Invocation(False, "", "", 0)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        expect(first.ok, result, "first deconstruction failed")
        expect(rebuilt.ok, result, "rebuild failed")
        expect(second.ok, result, "second deconstruction failed")
        if first.ok and second.ok:
            diffs = diff_snapshots(snapshot_tree(first_dir), snapshot_tree(second_dir))
            result.stats["drift_count"] = len(diffs)
            result.stats["first_files"] = len(snapshot_tree(first_dir))
            result.stats["second_files"] = len(snapshot_tree(second_dir))
            if diffs:
                result.warnings.append("; ".join(diffs[:8]) + (f" (+{len(diffs) - 8} more)" if len(diffs) > 8 else ""))
    except Exception as exc:  # pragma: no cover
        result.errors.append(f"Exception: {exc}")
        result.errors.append(traceback.format_exc())
    result.passed = not result.errors
    return result


def main() -> int:
    TEST_OUTPUT.mkdir(parents=True, exist_ok=True)
    results: list[TestResult] = []

    print("=" * 72)
    print("ProseDown CLI Test Suite")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 72)

    print("\n-- Unit Tests --")
    for result in run_algorithm_tests():
        results.append(result)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name}")
        for error in result.errors:
            print(f"  ERROR: {error}")

    print("\n-- Regression Tests --")
    for result in run_regression_tests():
        results.append(result)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name}")
        for error in result.errors:
            print(f"  ERROR: {error}")

    print("\n-- Build Examples --")
    for name, source in [("my-essay", EXAMPLE_SINGLE), ("multi-chapter", EXAMPLE_MULTI)]:
        result = run_build_example_test(name, source)
        results.append(result)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name} {result.stats}")
        for error in result.errors:
            print(f"  ERROR: {error}")

    print("\n-- Example Round-Trips --")
    for name, source in [("my-essay", EXAMPLE_SINGLE), ("multi-chapter", EXAMPLE_MULTI)]:
        result = run_example_roundtrip_test(name, source)
        results.append(result)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.name} {result.stats}")
        for error in result.errors:
            print(f"  ERROR: {error}")

    if STANDARD_EPUBS:
        print("\n-- Standard Ebooks Deconstruct --")
        for epub_path in STANDARD_EPUBS:
            result = run_deconstruct_fixture_test(epub_path, "standard-deconstruct")
            results.append(result)
            print(f"[{'PASS' if result.passed else 'FAIL'}] {epub_path.name} {result.stats}")
            for error in result.errors:
                print(f"  ERROR: {error}")

        print("\n-- Standard Ebooks Round-Trip Drift --")
        for epub_path in STANDARD_EPUBS:
            result = run_standard_roundtrip_test(epub_path)
            results.append(result)
            print(f"[{'PASS' if result.passed else 'FAIL'}] {epub_path.name} {result.stats}")
            for warning in result.warnings[:1]:
                print(f"  WARN: {warning}")
            for error in result.errors:
                print(f"  ERROR: {error}")

    if COMMERCIAL_EPUBS:
        print("\n-- Commercial EPUB Deconstruct --")
        for epub_path in COMMERCIAL_EPUBS:
            result = run_deconstruct_fixture_test(epub_path, "commercial-deconstruct")
            results.append(result)
            print(f"[{'PASS' if result.passed else 'FAIL'}] {epub_path.name[:64]} {result.stats}")
            for error in result.errors:
                print(f"  ERROR: {error}")

    if not (STANDARD_EPUBS or COMMERCIAL_EPUBS or GOOGLE_DOCS_EPUB or GUTENBERG_PG1342):
        print(
            "\n-- Corpus Tests --\n"
            f"Skipped: no corpus found at {CORPUS_ROOT}.\n"
            "Set PROSEDOWN_CORPUS=/path/to/corpus to run corpus tests locally."
        )

    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_category.setdefault(result.category, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(result.passed)
        bucket["failed"] += int(not result.passed)

    print("\n" + "=" * 72)
    print(f"TOTAL: {total} tests | {passed} passed | {failed} failed")
    for category, stats in sorted(by_category.items()):
        print(f"{category}: {stats['passed']}/{stats['total']} passed")
    print("=" * 72)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "by_category": by_category,
                },
                "results": [result.to_dict() for result in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nReport written to {REPORT_PATH}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
