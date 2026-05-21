"""
WikiCollection SQLAlchemy Model

Represents a collection of generated wiki pages derived from a single source.
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


class WikiCollection(Base):
    """
    A wiki collection represents a group of generated wiki pages.

    Attributes:
        id: Unique identifier for the collection.
        dataset_id: Reference to the M-flow dataset this collection belongs to.
        source_data_id: Reference to the source data item.
        title: Human-readable title of the collection.
        status: Current status (processing, ready, failed, upgrading, upgraded).
        error_message: Error details if processing failed.
        owner_id: User who owns this collection.
        tenant_id: Multi-tenant support.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "wiki_collections"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id = Column(PG_UUID(as_uuid=True), index=True, nullable=False)
    source_data_id = Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    title = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    error_message = Column(Text, nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), index=True, nullable=False)
    tenant_id = Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationship to pages
    pages = relationship(
        "WikiPage",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<WikiCollection(id={self.id}, title='{self.title}', status='{self.status}')>"
