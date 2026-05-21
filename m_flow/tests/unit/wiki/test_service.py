"""
Wiki Service Tests

Tests for wiki creation, search, and upgrade functionality.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from m_flow.shared.files.storage.config import file_storage_config
from m_flow.wiki.generator import generate_wiki_pages
from m_flow.wiki.service import create_wiki_from_text, search_wiki_pages


@dataclass
class FakeUser:
    """Fake user for testing."""

    id: object
    tenant_id: object | None = None


@dataclass
class FakePage:
    """Fake wiki page for testing search."""

    title: str
    path: str
    excerpt: str
    file_uri: str


@pytest.mark.asyncio
async def test_create_wiki_from_text_writes_markdown_and_metadata(tmp_path):
    """create_wiki_from_text should write markdown files and create metadata."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        user = FakeUser(id=uuid4())
        result = await create_wiki_from_text(
            content="# Intro\nAlpha content\n\n# Chapter One\nBeta content",
            dataset_name="book",
            user=user,
            add_func=None,
            session_factory=None,
        )

        assert result.collection.title == "book"
        assert result.collection.status == "ready"
        assert result.pages
        assert all(page.file_uri.startswith("file://") for page in result.pages)

        # Verify index.md exists
        index_path = tmp_path / "wiki" / str(result.collection.id) / "index.md"
        assert index_path.exists()
    finally:
        file_storage_config.reset(token)



@pytest.mark.asyncio
async def test_create_wiki_from_text_generates_correct_page_types(tmp_path):
    """create_wiki_from_text should generate index, summary, and chapter pages."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        user = FakeUser(id=uuid4())
        result = await create_wiki_from_text(
            content="# Section 1\nContent 1\n\n# Section 2\nContent 2",
            dataset_name="test",
            user=user,
            add_func=None,
            session_factory=None,
        )

        page_types = {p.page_type for p in result.pages}
        assert "index" in page_types
        assert "summary" in page_types
        assert "chapter" in page_types

        chapter_pages = [p for p in result.pages if p.page_type == "chapter"]
        assert len(chapter_pages) == 2
    finally:
        file_storage_config.reset(token)


@pytest.mark.asyncio
async def test_create_wiki_from_text_sets_correct_owner(tmp_path):
    """create_wiki_from_text should set owner_id from user."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        user_id = uuid4()
        user = FakeUser(id=user_id)
        result = await create_wiki_from_text(
            content="# Test\nTest content",
            dataset_name="test",
            user=user,
            add_func=None,
            session_factory=None,
        )

        assert result.collection.owner_id == user_id
    finally:
        file_storage_config.reset(token)


def test_search_wiki_pages_matches_title(tmp_path):
    """search_wiki_pages should match query in page title."""
    page_path = tmp_path / "page.md"
    page_path.write_text("# Page\nNeedle text", encoding="utf-8")

    pages = [
        FakePage(
            title="Test Page",
            path="page.md",
            excerpt="Preview",
            file_uri="file://" + str(page_path),
        )
    ]

    results = search_wiki_pages(pages, "test")
    assert len(results) == 1
    assert results[0]["title"] == "Test Page"


def test_search_wiki_pages_matches_content(tmp_path):
    """search_wiki_pages should match query in page content."""
    page_path = tmp_path / "page.md"
    page_path.write_text("# Page\nThis text contains the needle", encoding="utf-8")

    pages = [
        FakePage(
            title="Page",
            path="page.md",
            excerpt="Preview",
            file_uri="file://" + str(page_path),
        )
    ]

    results = search_wiki_pages(pages, "needle")
    assert len(results) == 1


def test_search_wiki_pages_no_match(tmp_path):
    """search_wiki_pages should return empty for no match."""
    page_path = tmp_path / "page.md"
    page_path.write_text("# Page\nContent here", encoding="utf-8")

    pages = [
        FakePage(
            title="Page",
            path="page.md",
            excerpt="Preview",
            file_uri="file://" + str(page_path),
        )
    ]

    results = search_wiki_pages(pages, "nonexistent")
    assert len(results) == 0


def test_search_wiki_pages_handles_missing_file(tmp_path):
    """search_wiki_pages should handle missing file gracefully."""
    pages = [
        FakePage(
            title="Page",
            path="page.md",
            excerpt="Preview",
            file_uri="file:///nonexistent/page.md",
        )
    ]

    # Should not raise, just skip the file
    results = search_wiki_pages(pages, "test")
    # Only matches if title/excerpt contains query
    assert isinstance(results, list)


def test_search_wiki_pages_case_insensitive(tmp_path):
    """search_wiki_pages should be case insensitive."""
    page_path = tmp_path / "page.md"
    page_path.write_text("# Page\nNEEDLE text", encoding="utf-8")

    pages = [
        FakePage(
            title="page",
            path="page.md",
            excerpt="preview",
            file_uri="file://" + str(page_path),
        )
    ]

    results = search_wiki_pages(pages, "Needle")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_create_wiki_from_text_with_tenant(tmp_path):
    """create_wiki_from_text should handle tenant_id if present."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        user_id = uuid4()
        tenant_id = uuid4()
        user = FakeUser(id=user_id, tenant_id=tenant_id)
        result = await create_wiki_from_text(
            content="# Test\nContent",
            dataset_name="test",
            user=user,
            add_func=None,
            session_factory=None,
        )

        assert result.collection.tenant_id == tenant_id
    finally:
        file_storage_config.reset(token)