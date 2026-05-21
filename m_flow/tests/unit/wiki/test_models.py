"""
Wiki Model Tests

Tests for WikiCollection and WikiPage SQLAlchemy models.
"""

from __future__ import annotations

from uuid import uuid4

from m_flow.adapters.relational import Base
from m_flow.wiki.models import WikiCollection, WikiPage


def test_wiki_models_are_registered_with_base_metadata():
    """Verify models are registered with SQLAlchemy Base."""
    assert WikiCollection.__tablename__ in Base.metadata.tables
    assert WikiPage.__tablename__ in Base.metadata.tables


def test_wiki_page_stores_file_uri_not_content_body():
    """WikiPage should store file_uri reference, not content body."""
    collection = WikiCollection(
        id=uuid4(),
        dataset_id=uuid4(),
        source_data_id=uuid4(),
        title="Example Book",
        status="ready",
        owner_id=uuid4(),
    )
    page = WikiPage(
        id=uuid4(),
        collection_id=collection.id,
        path="index.md",
        file_uri="file://E:/AIProject/m_flow/.data_storage/wiki/example/index.md",
        title="Index",
        content_hash="abc123",
        page_type="index",
        source_hash="source-hash",
        excerpt="Short preview",
    )

    assert page.file_uri.endswith("/index.md")
    assert not hasattr(page, "content")
    assert page.content_hash == "abc123"
    assert page.page_type == "index"


def test_wiki_collection_has_expected_columns():
    """WikiCollection should have all required columns."""
    collection = WikiCollection(
        id=uuid4(),
        dataset_id=uuid4(),
        source_data_id=uuid4(),
        title="Test Collection",
        status="processing",
        owner_id=uuid4(),
    )

    assert collection.title == "Test Collection"
    assert collection.status == "processing"
    assert collection.error_message is None
