"""
Wiki API Router

FastAPI router for wiki operations.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

# Binary document extensions that require specialized parsing
_BINARY_EXTENSIONS = frozenset([".docx", ".doc", ".pdf", ".pptx", ".ppt", ".xlsx", ".xls", ".odt", ".rtf", ".epub"])


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

    async def _extract_text_from_binary(raw_bytes: bytes, filename: str) -> str:
        """Extract text from binary document formats (docx, pdf, etc.)."""
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        from m_flow.shared.logging_utils import get_logger

        _log = get_logger(__name__)
        ext = Path(filename).suffix.lower()

        # --- .docx: parse ZIP + XML using stdlib ---
        if ext in (".docx", ".doc"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                    # word/document.xml contains the main text
                    with zf.open("word/document.xml") as doc_xml:
                        tree = ET.parse(doc_xml)
                        root = tree.getroot()

                        # Define namespace map
                        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

                        paragraphs = []
                        for para in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                            texts = []
                            for t_elem in para.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                                if t_elem.text:
                                    texts.append(t_elem.text)
                            line = "".join(texts).strip()
                            if line:
                                paragraphs.append(line)

                        if paragraphs:
                            return "\n\n".join(paragraphs)
            except Exception as exc:
                _log.warning("docx stdlib parsing failed for %s: %s", filename, exc)

        # --- .pdf: use pypdf ---
        if ext == ".pdf":
            try:
                from pypdf import PdfReader

                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path = tmp.name

                try:
                    reader = PdfReader(tmp_path)
                    pages = []
                    for page in reader.pages:
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append(text)
                    if pages:
                        return "\n\n".join(pages)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except ImportError:
                _log.warning("pypdf not available for PDF extraction")
            except Exception as exc:
                _log.warning("pypdf parsing failed for %s: %s", filename, exc)

        # --- Fallback: try unstructured library ---
        try:
            from unstructured.partition.auto import partition

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            try:
                elements = partition(filename=tmp_path, strategy="fast")
                segments = [str(el).strip() for el in elements if str(el).strip()]
                if segments:
                    return "\n\n".join(segments)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except ImportError:
            _log.warning("unstructured library not available for %s", ext)
        except Exception as exc:
            _log.error("unstructured partition failed for %s: %s", filename, exc)

        # Last resort: try text decoding
        _log.warning("Falling back to raw text decode for binary file %s", filename)
        return raw_bytes.decode("utf-8", errors="replace")

    @router.post("/ingest/upload", response_model=WikiCollectionResponse)
    async def ingest_upload(
        data: list[UploadFile] = File(...),
        datasetName: Optional[str] = Form(default=None),
        upgrade_after_ingest: bool = Form(default=False),
        user=Depends(_auth()),
    ):
        """
        Ingest uploaded files as wiki.

        Supports text files (.txt, .md, .csv) and binary documents
        (.docx, .pdf, .pptx, etc.). Binary documents are parsed using
        unstructured/pypdf libraries.
        """
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.service import create_wiki_from_text

        content_parts = []
        original_files: list[tuple[str, bytes]] = []  # (filename, raw_bytes)

        for item in data:
            raw_bytes = await item.read()
            filename = item.filename or "unknown"
            ext = Path(filename).suffix.lower()

            # Save original file for archival
            original_files.append((filename, raw_bytes))

            if ext in _BINARY_EXTENSIONS:
                # Binary document: use specialized parser
                content = await _extract_text_from_binary(raw_bytes, filename)
            else:
                # Text file: try multiple encodings
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
            original_files=original_files,
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