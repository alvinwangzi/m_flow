"""
WikiPage SQLAlchemy Model

Represents a single generated wiki page with disk-backed markdown storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from m_flow.adapters.relational import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WikiPage(Base):
    """
    A wiki page represents a single generated markdown file.

    Note: Content is stored on disk, not in the database.
    Only metadata (path, title, hashes, excerpt) is stored in SQL.

    Attributes:
        id: Unique identifier for the page.
        collection_id: Reference to the parent WikiCollection.
        path: Relative path within the collection (e.g., "chapters/intro.md").
        file_uri: Absolute file:// URI to the markdown file on disk.
        title: Page title (extracted from first heading).
        content_hash: MD5 hash of the generated content.
        page_type: Page type (index, summary, chapter, etc.).
        source_hash: MD5 hash of the source text this page was generated from.
        excerpt: Short preview text for search results.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "wiki_pages"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    collection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("wiki_collections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    path = Column(String(1024), nullable=False)
    file_uri = Column(String(2048), nullable=False)
    title = Column(String(512), nullable=False)
    content_hash = Column(String(128), nullable=False)
    page_type = Column(String(32), nullable=False)
    source_hash = Column(String(128), nullable=False)
    excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationship back to collection
    collection = relationship("WikiCollection", back_populates="pages")

    def __repr__(self) -> str:
        return f"<WikiPage(id={self.id}, path='{self.path}', title='{self.title}')>"
