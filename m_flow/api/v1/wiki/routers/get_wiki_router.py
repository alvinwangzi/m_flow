"""
Wiki API Router

FastAPI router for wiki operations.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field


class WikiIngestRequest(BaseModel):
    """Request model for wiki text ingestion."""

    content: str
    dataset_name: Optional[str] = None
    upgrade_after_ingest: bool = False


class WikiCollectionResponse(BaseModel):
    """Response model for wiki collection."""

    id: str
    dataset_id: str
    title: str
    status: str


def _auth():
    """Return the user authentication dependency."""
    from m_flow.auth.methods import get_authenticated_user

    return get_authenticated_user


def get_wiki_router() -> APIRouter:
    """
    Construct the wiki API router.

    Provides endpoints for:
    - POST /ingest: Text content ingestion
    - POST /ingest/upload: File upload ingestion
    - GET /collections/{collection_id}: Get collection details
    - GET /collections/{collection_id}/pages: List collection pages
    - GET /pages/{page_id}: Get page details
    - POST /collections/{collection_id}/upgrade: Upgrade to M-flow memorize
    """
    router = APIRouter()

    @router.post("/ingest", response_model=WikiCollectionResponse)
    async def ingest_text(request: WikiIngestRequest, user=Depends(_auth())):
        """
        Ingest text content as wiki.

        Generates wiki pages from text content and stores metadata.
        """
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.service import create_wiki_from_text

        db = get_db_adapter()
        result = await create_wiki_from_text(
            content=request.content,
            dataset_name=request.dataset_name or "main_dataset",
            user=user,
            add_func=None,
            session_factory=db.get_async_session,
            upgrade_after_ingest=request.upgrade_after_ingest,
        )
        return {
            "id": str(result.collection.id),
            "dataset_id": str(result.collection.dataset_id),
            "title": result.collection.title,
            "status": result.collection.status,
        }

    @router.post("/ingest/upload", response_model=WikiCollectionResponse)
    async def ingest_upload(
        data: list[UploadFile] = File(...),
        datasetName: Optional[str] = Form(default=None),
        upgrade_after_ingest: bool = Form(default=False),
        user=Depends(_auth()),
    ):
        """
        Ingest uploaded files as wiki.

        Reads uploaded files and generates wiki pages.
        """
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.service import create_wiki_from_text

        content_parts = []
        for item in data:
            # Try multiple encodings to handle various file encodings
            raw_bytes = await item.read()
            content = None
            for encoding in ["utf-8", "gbk", "gb2312", "gb18030"]:
                try:
                    content = raw_bytes.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if content is None:
                content = raw_bytes.decode("utf-8", errors="replace")
            content_parts.append(content)

        db = get_db_adapter()
        result = await create_wiki_from_text(
            content="\n\n".join(content_parts),
            dataset_name=datasetName or "main_dataset",
            user=user,
            add_func=None,
            session_factory=db.get_async_session,
            upgrade_after_ingest=upgrade_after_ingest,
        )
        return {
            "id": str(result.collection.id),
            "dataset_id": str(result.collection.dataset_id),
            "title": result.collection.title,
            "status": result.collection.status,
        }

    @router.get("/collections/{collection_id}", response_model=WikiCollectionResponse)
    async def get_collection(collection_id: UUID, user=Depends(_auth())):
        """Get collection details by ID."""
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.models import WikiCollection

        db = get_db_adapter()
        async with db.get_async_session() as session:
            collection = await session.get(WikiCollection, collection_id)
            if collection is None:
                return {
                    "id": str(collection_id),
                    "dataset_id": "",
                    "title": "Not Found",
                    "status": "not_found",
                }
            return {
                "id": str(collection.id),
                "dataset_id": str(collection.dataset_id),
                "title": collection.title,
                "status": collection.status,
            }

    @router.get("/collections/{collection_id}/pages")
    async def list_pages(collection_id: UUID, user=Depends(_auth())):
        """List all pages in a collection."""
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.models import WikiPage
        from sqlalchemy import select

        db = get_db_adapter()
        async with db.get_async_session() as session:
            stmt = select(WikiPage).where(WikiPage.collection_id == collection_id)
            result = await session.execute(stmt)
            pages = result.scalars().all()
            return {
                "collection_id": str(collection_id),
                "pages": [
                    {
                        "id": str(p.id),
                        "path": p.path,
                        "title": p.title,
                        "page_type": p.page_type,
                        "excerpt": p.excerpt,
                    }
                    for p in pages
                ],
            }

    @router.get("/pages/{page_id}")
    async def get_page(page_id: UUID, user=Depends(_auth())):
        """Get page details including content."""
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.models import WikiPage
        from m_flow.wiki.storage import WikiStorage

        db = get_db_adapter()
        async with db.get_async_session() as session:
            page = await session.get(WikiPage, page_id)
            if page is None:
                return {"id": str(page_id), "error": "Page not found"}

            storage = WikiStorage()
            content = ""
            try:
                content = storage.read_page(page.collection_id, page.path)
            except Exception:
                pass

            return {
                "id": str(page.id),
                "path": page.path,
                "title": page.title,
                "page_type": page.page_type,
                "content": content,
                "file_uri": page.file_uri,
            }

    @router.post("/collections/{collection_id}/upgrade", response_model=WikiCollectionResponse)
    async def upgrade_collection(collection_id: UUID, user=Depends(_auth())):
        """Trigger M-flow memorize upgrade for a wiki collection."""
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.models import WikiCollection
        from m_flow.wiki.service import upgrade_collection_to_mflow

        db = get_db_adapter()
        async with db.get_async_session() as session:
            collection = await session.get(WikiCollection, collection_id)
            if collection is None:
                return {
                    "id": str(collection_id),
                    "dataset_id": "",
                    "title": "Not Found",
                    "status": "not_found",
                }

            await upgrade_collection_to_mflow(collection)
            await session.commit()

            return {
                "id": str(collection.id),
                "dataset_id": str(collection.dataset_id),
                "title": collection.title,
                "status": collection.status,
            }

    return router