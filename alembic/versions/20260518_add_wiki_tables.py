"""
Add wiki tables

Revision ID: 20260518_wiki
Revises: 92b3293baa66
Create Date: 2026-05-18

This migration adds tables for wiki collections and pages.
Wiki pages store content on disk, not in the database.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260518_wiki"
down_revision: str = "92b3293baa66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create wiki_collections and wiki_pages tables."""
    # Create wiki_collections table
    op.create_table(
        "wiki_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_data_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_wiki_collections_dataset_id", "wiki_collections", ["dataset_id"])
    op.create_index("ix_wiki_collections_source_data_id", "wiki_collections", ["source_data_id"])
    op.create_index("ix_wiki_collections_owner_id", "wiki_collections", ["owner_id"])
    op.create_index("ix_wiki_collections_tenant_id", "wiki_collections", ["tenant_id"])

    # Create wiki_pages table
    op.create_table(
        "wiki_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wiki_collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("file_uri", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("page_type", sa.String(length=32), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_wiki_pages_collection_id", "wiki_pages", ["collection_id"])


def downgrade() -> None:
    """Drop wiki_pages and wiki_collections tables."""
    op.drop_index("ix_wiki_pages_collection_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
    op.drop_index("ix_wiki_collections_tenant_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_owner_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_source_data_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_dataset_id", table_name="wiki_collections")
    op.drop_table("wiki_collections")