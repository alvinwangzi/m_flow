"""
Wiki Service

High-level orchestration for wiki creation, search, and upgrade.
Coordinates source add, text extraction, page generation, metadata writes, and upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from m_flow.wiki.generator import generate_wiki_pages
from m_flow.wiki.models import WikiCollection, WikiPage
from m_flow.wiki.storage import WikiStorage


@dataclass
class WikiCreateResult:
    """Result of wiki creation containing collection and pages."""

    collection: WikiCollection
    pages: list[WikiPage]


def _file_uri_to_path(file_uri: str) -> Path:
    """Convert file:// URI to Path."""
    if not file_uri.startswith("file://"):
        raise ValueError(f"Unsupported Wiki page URI: {file_uri}")
    return Path(file_uri.replace("file://", "", 1))


async def create_wiki_from_text(
    *,
    content: str,
    dataset_name: str,
    user: Any,
    add_func: Callable[..., Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
    upgrade_after_ingest: bool = False,
    original_files: list[tuple[str, bytes]] | None = None,
) -> WikiCreateResult:
    """
    Create a wiki collection from text content.

    Generates markdown pages, writes them to disk, and optionally persists metadata.
    Preserves the original source document for reference.

    Args:
        content: Source text content (already extracted).
        dataset_name: Name for the wiki collection.
        user: User creating the wiki.
        add_func: Optional M-flow add() function for data ingestion.
        session_factory: Optional database session factory for metadata persistence.
        upgrade_after_ingest: If True, trigger M-flow memorize after creation.
        original_files: Optional list of (filename, raw_bytes) to preserve originals.

    Returns:
        WikiCreateResult with collection and pages.
    """
    collection_id = uuid4()
    dataset_id = uuid4()

    collection = WikiCollection(
        id=collection_id,
        dataset_id=dataset_id,
        source_data_id=None,
        title=dataset_name,
        status="processing",
        owner_id=user.id,
        tenant_id=getattr(user, "tenant_id", None),
    )

    storage = WikiStorage()
    pages: list[WikiPage] = []

    # Save original source files (preserving binary format)
    if original_files:
        for filename, raw_bytes in original_files:
            storage.write_binary(collection.id, f"_source/{filename}", raw_bytes)
    else:
        # Text-only ingest: save as text
        storage.write_page(collection.id, "_source/original.txt", content)

    for generated in generate_wiki_pages(dataset_name, content):
        file_uri = storage.write_page(collection.id, generated.path, generated.content)
        pages.append(
            WikiPage(
                id=uuid4(),
                collection_id=collection.id,
                path=generated.path,
                file_uri=file_uri,
                title=generated.title,
                content_hash=generated.content_hash,
                page_type=generated.page_type,
                source_hash=generated.source_hash,
                excerpt=generated.excerpt,
            )
        )

    # Update status to ready
    collection.status = "ready"

    # Persist to database if session factory provided
    if session_factory is not None:
        async with session_factory() as session:
            session.add(collection)
            for page in pages:
                session.add(page)
            await session.commit()

    return WikiCreateResult(collection=collection, pages=pages)


def search_wiki_pages(pages: list[Any], query: str) -> list[dict[str, str]]:
    """
    Search wiki pages by query.

    Searches in page title, path, excerpt, and full content.

    Args:
        pages: List of WikiPage objects to search.
        query: Search query string.

    Returns:
        List of matching pages with title, path, excerpt, and file_uri.
    """
    needle = query.lower()
    results: list[dict[str, str]] = []

    for page in pages:
        # Search metadata
        haystack = " ".join([page.title or "", page.path or "", page.excerpt or ""]).lower()

        # Search content if available
        content = ""
        try:
            content = _file_uri_to_path(page.file_uri).read_text(encoding="utf-8")
        except OSError:
            content = ""

        if needle in haystack or needle in content.lower():
            results.append(
                {
                    "title": page.title,
                    "path": page.path,
                    "excerpt": page.excerpt or "",
                    "file_uri": page.file_uri,
                }
            )

    return results


async def upgrade_collection_to_mflow(
    collection: WikiCollection,
    memorize_func: Callable[..., Any] | None = None,
) -> None:
    """
    Trigger M-flow memorize on a wiki collection.

    Updates collection status and triggers background processing.

    Args:
        collection: WikiCollection to upgrade.
        memorize_func: Optional M-flow memorize function.
    """
    collection.status = "upgrading"

    if memorize_func is None:
        # Lazy import to avoid circular dependency
        from m_flow.api.v1.memorize import memorize as _memorize

        memorize_func = _memorize

    await memorize_func(datasets=[collection.dataset_id], run_in_background=True)


async def delete_wiki_collection(
    collection_id: Any,
    session_factory: Callable[[], Any] | None = None,
) -> bool:
    """
    Delete a wiki collection and all its pages.

    Args:
        collection_id: UUID of the collection to delete.
        session_factory: Database session factory.

    Returns:
        True if deleted successfully.
    """
    from m_flow.wiki.models import WikiPage

    storage = WikiStorage()

    # Delete from database if session factory provided
    if session_factory is not None:
        async with session_factory() as session:
            # Delete pages first (cascade should handle this, but be explicit)
            await session.execute(
                __import__("sqlalchemy").delete(WikiPage).where(WikiPage.collection_id == collection_id)
            )

            # Delete collection
            collection = await session.get(WikiCollection, collection_id)
            if collection:
                await session.delete(collection)
                await session.commit()

    # Delete files from disk
    storage.delete_collection(collection_id)

    return True