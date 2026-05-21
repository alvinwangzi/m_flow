"""
Wiki Generation Tests

Tests for sectioning and page generation.
"""

from __future__ import annotations

from m_flow.wiki.generator import generate_wiki_pages
from m_flow.wiki.sectioning import split_into_sections, WikiSection


def test_split_into_sections_prefers_markdown_headings():
    """split_into_sections should prefer markdown heading-based splitting."""
    sections = split_into_sections("# Intro\nAlpha content\n\n# Chapter One\nBeta content", max_chars=1000)

    assert [s.title for s in sections] == ["Intro", "Chapter One"]
    assert sections[0].text == "Alpha content"
    assert sections[1].text == "Beta content"


def test_split_into_sections_falls_back_to_character_chunking():
    """split_into_sections should fallback to character chunking without headings."""
    long_text = "A" * 25
    sections = split_into_sections(long_text, max_chars=10)

    assert len(sections) == 3
    assert sections[0].title == "Section 1"


def test_split_into_sections_handles_h1_h3_headings():
    """split_into_sections should handle H1-H3 headings."""
    text = "# H1 Title\nH1 content\n\n## H2 Title\nH2 content\n\n### H3 Title\nH3 content"
    sections = split_into_sections(text)

    assert len(sections) == 3
    assert sections[0].title == "H1 Title"
    assert sections[1].title == "H2 Title"
    assert sections[2].title == "H3 Title"


def test_split_into_sections_ignores_h4_and_deeper():
    """split_into_sections should ignore H4+ headings."""
    text = "# Main\nMain content\n\n#### H4 Title\nThis is H4 content\n\n## Chapter\nChapter content"
    sections = split_into_sections(text)

    # H4 should be part of previous section
    assert len(sections) == 2
    assert "H4 Title" in sections[0].text


def test_generate_wiki_pages_returns_disk_paths_and_markdown():
    """generate_wiki_pages should return all expected pages with markdown content."""
    pages = generate_wiki_pages("Example", "# Intro\nAlpha content\n\n# Chapter One\nBeta content")

    paths = {p.path for p in pages}
    assert "index.md" in paths
    assert "summary.md" in paths
    assert "chapters/intro.md" in paths
    assert "chapters/chapter-one.md" in paths
    assert all(p.content.startswith("# ") for p in pages)


def test_generate_wiki_pages_content_structure():
    """Generated pages should have correct structure."""
    pages = generate_wiki_pages("Test Title", "# Section 1\nContent 1\n\n# Section 2\nContent 2")

    index_page = next(p for p in pages if p.path == "index.md")
    assert "Test Title" in index_page.content
    assert "目录" in index_page.content
    assert index_page.page_type == "index"

    summary_page = next(p for p in pages if p.path == "summary.md")
    assert "摘要" in summary_page.content
    assert summary_page.page_type == "summary"

    chapter_pages = [p for p in pages if p.page_type == "chapter"]
    assert len(chapter_pages) == 2


def test_generate_wiki_pages_handles_empty_sections():
    """generate_wiki_pages should handle empty input gracefully."""
    pages = generate_wiki_pages("Empty", "")

    # Should still generate index and summary
    paths = {p.path for p in pages}
    assert "index.md" in paths
    assert "summary.md" in paths


def test_generate_wiki_pages_content_hashes():
    """Generated pages should have valid content and source hashes."""
    pages = generate_wiki_pages("Test", "# Section\nContent")

    for page in pages:
        assert page.content_hash
        assert len(page.content_hash) == 32  # MD5 hash length
        assert page.source_hash
        assert len(page.source_hash) == 32


def test_generate_wiki_pages_excerpts():
    """Generated pages should have excerpts."""
    pages = generate_wiki_pages("Test", "# Section\n" + "x" * 500)

    for page in pages:
        assert page.excerpt
        assert len(page.excerpt) <= 240  # Default excerpt limit


def test_generate_wiki_pages_chinese_title_slug():
    """Slug generation should handle Chinese characters."""
    pages = generate_wiki_pages("测试", "# 简介\n内容\n\n# 第二章\n内容")

    chapter_paths = [p.path for p in pages if p.page_type == "chapter"]
    # Should not have empty slugs
    assert all(p for p in chapter_paths)


def test_wiki_section_dataclass_immutable():
    """WikiSection should be a frozen dataclass (immutable)."""
    section = WikiSection(title="Test", text="Content")

    with __import__("pytest").raises(__import__("dataclasses").FrozenInstanceError):
        section.title = "Changed"  # type: ignore