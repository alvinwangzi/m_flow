# Wiki Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent Wiki ingest path that writes generated Markdown pages to disk, stores only metadata in SQL, supports lightweight Wiki search, and can upgrade a Wiki collection through the existing M-flow `memorize()` pipeline.

**Architecture:** Add a separate `m_flow/api/v1/wiki/` vertical slice with SQLAlchemy models, disk-backed page storage, a small generation pipeline, and a FastAPI router. Keep existing `/api/v1/ingest`, `add()`, and `memorize()` behavior unchanged; frontend import mode selection calls the new Wiki API when users choose Wiki modes.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, existing M-flow storage config, existing `add()` / loader infrastructure, pytest, Next.js/TypeScript frontend API client.

---

## File Structure

- Create `m_flow/wiki/models/WikiCollection.py`: SQLAlchemy model for Wiki collection metadata.
- Create `m_flow/wiki/models/WikiPage.py`: SQLAlchemy model for disk-backed Wiki page metadata.
- Create `m_flow/wiki/models/__init__.py`: exports Wiki models so `Base.metadata` sees them.
- Create `m_flow/wiki/storage.py`: maps collection/page paths to `<DATA_ROOT_DIRECTORY>/wiki/<collection_id>/...`, writes and reads Markdown safely.
- Create `m_flow/wiki/sectioning.py`: simple heading-based and fallback section splitter.
- Create `m_flow/wiki/generator.py`: deterministic v1 page generator with injectable LLM hook later.
- Create `m_flow/wiki/service.py`: orchestrates source add, text extraction, page generation, metadata writes, search, and upgrade.
- Create `m_flow/api/v1/wiki/routers/get_wiki_router.py`: FastAPI router.
- Create `m_flow/api/v1/wiki/__init__.py`: router export.
- Modify `m_flow/api/client.py`: mount `/api/v1/wiki`.
- Create Alembic migration `alembic/versions/<revision>_add_wiki_tables.py`: creates `wiki_collections` and `wiki_pages`.
- Modify `m_flow/data/models/__init__.py` or import Wiki models in an existing metadata import path if needed.
- Create backend tests under `m_flow/tests/unit/wiki/`.
- Modify `m_flow-frontend/src/types/index.ts`: Wiki request/response types and processing mode.
- Modify `m_flow-frontend/src/lib/api/client.ts`: Wiki API client methods.
- Modify upload/import component used by Quick Import, likely `m_flow-frontend/src/components/upload/FileUpload.tsx`, to add processing mode selector and call Wiki API for Wiki modes.

## Task 1: Add Wiki SQL Models

**Files:**
- Create: `m_flow/wiki/models/WikiCollection.py`
- Create: `m_flow/wiki/models/WikiPage.py`
- Create: `m_flow/wiki/models/__init__.py`
- Create: `m_flow/wiki/__init__.py`
- Test: `m_flow/tests/unit/wiki/test_models.py`

- [ ] **Step 1: Write the failing model test**

Create `m_flow/tests/unit/wiki/test_models.py`:

```python
from __future__ import annotations

from uuid import uuid4

from m_flow.adapters.relational import Base
from m_flow.wiki.models import WikiCollection, WikiPage


def test_wiki_models_are_registered_with_base_metadata():
    assert WikiCollection.__tablename__ in Base.metadata.tables
    assert WikiPage.__tablename__ in Base.metadata.tables


def test_wiki_page_stores_file_uri_not_content_body():
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
        content_hash="hash",
        page_type="index",
        source_hash="source-hash",
        excerpt="Short preview",
    )

    assert page.file_uri.endswith("/index.md")
    assert not hasattr(page, "content")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'm_flow.wiki'`.

- [ ] **Step 3: Implement models**

Create `m_flow/wiki/__init__.py`:

```python
"""Disk-backed Wiki ingestion package."""
```

Create `m_flow/wiki/models/WikiCollection.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from m_flow.adapters.relational import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WikiCollection(Base):
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

    pages = relationship("WikiPage", back_populates="collection", cascade="all, delete-orphan")
```

Create `m_flow/wiki/models/WikiPage.py`:

```python
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

    collection = relationship("WikiCollection", back_populates="pages")
```

Create `m_flow/wiki/models/__init__.py`:

```python
from .WikiCollection import WikiCollection as WikiCollection
from .WikiPage import WikiPage as WikiPage
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add m_flow/wiki m_flow/tests/unit/wiki/test_models.py
git commit -s -m "feat(wiki): add wiki metadata models"
```

## Task 2: Add Alembic Migration

**Files:**
- Create: `alembic/versions/<revision>_add_wiki_tables.py`
- Test: `m_flow/tests/unit/wiki/test_migration_imports.py`

- [ ] **Step 1: Write migration structure test**

Create `m_flow/tests/unit/wiki/test_migration_imports.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_wiki_migration_exists_and_creates_tables():
    migration_files = list(Path("alembic/versions").glob("*_add_wiki_tables.py"))
    assert migration_files, "Expected add_wiki_tables migration"
    content = migration_files[0].read_text(encoding="utf-8")
    assert "wiki_collections" in content
    assert "wiki_pages" in content
    assert "file_uri" in content
    assert 'Column("content"' not in content
    assert 'sa.Column("content"' not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_migration_imports.py -q
```

Expected: FAIL because migration file does not exist.

- [ ] **Step 3: Create migration**

Create `alembic/versions/20260515_add_wiki_tables.py`:

```python
"""add wiki tables

Revision ID: 20260515_wiki
Revises: 92b3293baa66
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260515_wiki"
down_revision = "92b3293baa66"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.create_table(
        "wiki_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("file_uri", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("page_type", sa.String(length=32), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["collection_id"], ["wiki_collections.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_wiki_pages_collection_id", "wiki_pages", ["collection_id"])


def downgrade() -> None:
    op.drop_index("ix_wiki_pages_collection_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
    op.drop_index("ix_wiki_collections_tenant_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_owner_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_source_data_id", table_name="wiki_collections")
    op.drop_index("ix_wiki_collections_dataset_id", table_name="wiki_collections")
    op.drop_table("wiki_collections")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_migration_imports.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/20260515_add_wiki_tables.py m_flow/tests/unit/wiki/test_migration_imports.py
git commit -s -m "feat(wiki): add wiki table migration"
```

## Task 3: Add Disk-Backed Markdown Storage

**Files:**
- Create: `m_flow/wiki/storage.py`
- Test: `m_flow/tests/unit/wiki/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create `m_flow/tests/unit/wiki/test_storage.py`:

```python
from __future__ import annotations

from uuid import uuid4

from m_flow.shared.files.storage.config import file_storage_config
from m_flow.wiki.storage import WikiStorage


def test_wiki_storage_writes_markdown_under_data_root(tmp_path):
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()
        file_uri = storage.write_page(collection_id, "chapters/chapter-01.md", "# Chapter\nBody")

        expected = tmp_path / "wiki" / str(collection_id) / "chapters" / "chapter-01.md"
        assert expected.read_text(encoding="utf-8") == "# Chapter\nBody"
        assert file_uri == "file://" + str(expected)
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_rejects_path_traversal(tmp_path):
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        storage = WikiStorage()
        try:
            storage.write_page(uuid4(), "../escape.md", "bad")
        except ValueError as exc:
            assert "Unsafe wiki page path" in str(exc)
        else:
            raise AssertionError("Expected ValueError")
    finally:
        file_storage_config.reset(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_storage.py -q
```

Expected: FAIL because `m_flow.wiki.storage` does not exist.

- [ ] **Step 3: Implement storage**

Create `m_flow/wiki/storage.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from m_flow.shared.files.storage import get_storage_config


class WikiStorage:
    """Disk-backed storage for generated Wiki Markdown pages."""

    def __init__(self, root_dir: str | None = None) -> None:
        cfg = get_storage_config()
        self.root_dir = Path(root_dir or cfg["data_root_directory"]).resolve()

    def collection_dir(self, collection_id: UUID) -> Path:
        return self.root_dir / "wiki" / str(collection_id)

    def resolve_page_path(self, collection_id: UUID, relative_path: str) -> Path:
        rel = Path(relative_path.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe wiki page path: {relative_path}")
        target = (self.collection_dir(collection_id) / rel).resolve()
        base = self.collection_dir(collection_id).resolve()
        if os.path.commonpath([str(base), str(target)]) != str(base):
            raise ValueError(f"Unsafe wiki page path: {relative_path}")
        return target

    def write_page(self, collection_id: UUID, relative_path: str, content: str) -> str:
        target = self.resolve_page_path(collection_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return "file://" + str(target)

    def read_page(self, collection_id: UUID, relative_path: str) -> str:
        return self.resolve_page_path(collection_id, relative_path).read_text(encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_storage.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add m_flow/wiki/storage.py m_flow/tests/unit/wiki/test_storage.py
git commit -s -m "feat(wiki): store markdown pages on disk"
```

## Task 4: Add Sectioning and Page Generation

**Files:**
- Create: `m_flow/wiki/sectioning.py`
- Create: `m_flow/wiki/generator.py`
- Test: `m_flow/tests/unit/wiki/test_generation.py`

- [ ] **Step 1: Write failing generation tests**

Create `m_flow/tests/unit/wiki/test_generation.py`:

```python
from __future__ import annotations

from m_flow.wiki.generator import generate_wiki_pages
from m_flow.wiki.sectioning import split_into_sections


def test_split_into_sections_prefers_markdown_headings():
    sections = split_into_sections("# Intro\nAlpha\n\n# Chapter One\nBeta", max_chars=1000)

    assert [s.title for s in sections] == ["Intro", "Chapter One"]
    assert sections[0].text == "Alpha"
    assert sections[1].text == "Beta"


def test_split_into_sections_falls_back_to_windows():
    sections = split_into_sections("A" * 25, max_chars=10)

    assert len(sections) == 3
    assert sections[0].title == "Section 1"


def test_generate_wiki_pages_returns_disk_paths_and_markdown():
    pages = generate_wiki_pages("Example", "# Intro\nAlpha")

    paths = {p.path for p in pages}
    assert "index.md" in paths
    assert "summary.md" in paths
    assert "chapters/intro.md" in paths
    assert all(p.content.startswith("# ") for p in pages)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_generation.py -q
```

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement sectioning**

Create `m_flow/wiki/sectioning.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WikiSection:
    title: str
    text: str
    source_hash: str = ""


def split_into_sections(text: str, max_chars: int = 12000) -> list[WikiSection]:
    heading_pattern = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))
    if matches:
        sections: list[WikiSection] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(WikiSection(title=match.group(1).strip(), text=body))
        if sections:
            return sections

    chunks = [text[i : i + max_chars].strip() for i in range(0, len(text), max_chars)]
    return [WikiSection(title=f"Section {i + 1}", text=chunk) for i, chunk in enumerate(chunks) if chunk]
```

- [ ] **Step 4: Implement generator**

Create `m_flow/wiki/generator.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .sectioning import WikiSection, split_into_sections


@dataclass(frozen=True)
class GeneratedWikiPage:
    path: str
    title: str
    content: str
    page_type: str
    content_hash: str
    source_hash: str
    excerpt: str


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title.strip()).strip("-").lower()
    return slug or "section"


def _excerpt(text: str, limit: int = 240) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit]


def _chapter_page(section: WikiSection) -> GeneratedWikiPage:
    source_hash = _hash(section.text)
    title = section.title
    content = f"# {title}\n\n## 摘要\n\n{_excerpt(section.text, 800)}\n"
    return GeneratedWikiPage(
        path=f"chapters/{_slug(title)}.md",
        title=title,
        content=content,
        page_type="chapter",
        content_hash=_hash(content),
        source_hash=source_hash,
        excerpt=_excerpt(section.text),
    )


def generate_wiki_pages(title: str, text: str) -> list[GeneratedWikiPage]:
    sections = split_into_sections(text)
    chapter_pages = [_chapter_page(section) for section in sections]
    links = "\n".join(f"- [{page.title}]({page.path})" for page in chapter_pages)
    summary = _excerpt(text, 1200)
    index_content = f"# {title}\n\n## 目录\n\n{links}\n"
    summary_content = f"# {title} 摘要\n\n{summary}\n"
    return [
        GeneratedWikiPage(
            path="index.md",
            title=title,
            content=index_content,
            page_type="index",
            content_hash=_hash(index_content),
            source_hash=_hash(text),
            excerpt=_excerpt(index_content),
        ),
        GeneratedWikiPage(
            path="summary.md",
            title=f"{title} 摘要",
            content=summary_content,
            page_type="summary",
            content_hash=_hash(summary_content),
            source_hash=_hash(text),
            excerpt=_excerpt(summary),
        ),
        *chapter_pages,
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/wiki/test_generation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add m_flow/wiki/sectioning.py m_flow/wiki/generator.py m_flow/tests/unit/wiki/test_generation.py
git commit -s -m "feat(wiki): generate markdown wiki pages"
```

## Task 5: Add Wiki Service

**Files:**
- Create: `m_flow/wiki/service.py`
- Test: `m_flow/tests/unit/wiki/test_service.py`

- [ ] **Step 1: Write service tests with dependency injection**

Create `m_flow/tests/unit/wiki/test_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from m_flow.shared.files.storage.config import file_storage_config
from m_flow.wiki.service import create_wiki_from_text, search_wiki_pages


@dataclass
class FakeUser:
    id: object
    tenant_id: object | None = None


@pytest.mark.asyncio
async def test_create_wiki_from_text_writes_markdown_and_metadata(tmp_path):
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        user = FakeUser(id=uuid4())
        result = await create_wiki_from_text(
            content="# Intro\nAlpha",
            dataset_name="book",
            user=user,
            add_func=None,
            session_factory=None,
        )

        assert result.collection.title == "book"
        assert result.pages
        assert all(page.file_uri.startswith("file://") for page in result.pages)
        assert (tmp_path / "wiki" / str(result.collection.id) / "index.md").exists()
    finally:
        file_storage_config.reset(token)


def test_search_wiki_pages_reads_markdown_files(tmp_path):
    page_path = tmp_path / "page.md"
    page_path.write_text("# Page\nNeedle text", encoding="utf-8")

    class Page:
        title = "Page"
        path = "page.md"
        excerpt = "Preview"
        file_uri = "file://" + str(page_path)

    results = search_wiki_pages([Page()], "needle")

    assert len(results) == 1
    assert results[0]["title"] == "Page"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest m_flow/tests/unit/wiki/test_service.py -q
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement minimal service**

Create `m_flow/wiki/service.py`:

```python
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
    collection: WikiCollection
    pages: list[WikiPage]


def _file_uri_to_path(file_uri: str) -> Path:
    if not file_uri.startswith("file://"):
        raise ValueError(f"Unsupported Wiki page URI: {file_uri}")
    return Path(file_uri.replace("file://", "", 1))


async def create_wiki_from_text(
    *,
    content: str,
    dataset_name: str,
    user: Any,
    add_func: Callable[..., Any] | None,
    session_factory: Callable[[], Any] | None,
    upgrade_after_ingest: bool = False,
) -> WikiCreateResult:
    collection = WikiCollection(
        id=uuid4(),
        dataset_id=uuid4(),
        source_data_id=None,
        title=dataset_name,
        status="ready",
        owner_id=user.id,
        tenant_id=getattr(user, "tenant_id", None),
    )
    storage = WikiStorage()
    pages: list[WikiPage] = []
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
    if session_factory is not None:
        async with session_factory() as session:
            session.add(collection)
            for page in pages:
                session.add(page)
            await session.commit()
    return WikiCreateResult(collection=collection, pages=pages)


def search_wiki_pages(pages: list[Any], query: str) -> list[dict[str, str]]:
    needle = query.lower()
    results: list[dict[str, str]] = []
    for page in pages:
        haystack = " ".join([page.title or "", page.path or "", page.excerpt or ""]).lower()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest m_flow/tests/unit/wiki/test_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add m_flow/wiki/service.py m_flow/tests/unit/wiki/test_service.py
git commit -s -m "feat(wiki): add wiki creation service"
```

## Task 6: Add Wiki API Router

**Files:**
- Create: `m_flow/api/v1/wiki/routers/get_wiki_router.py`
- Create: `m_flow/api/v1/wiki/routers/__init__.py`
- Create: `m_flow/api/v1/wiki/__init__.py`
- Modify: `m_flow/api/client.py`
- Test: `m_flow/tests/unit/api/test_wiki_router.py`

- [ ] **Step 1: Write router registration test**

Create `m_flow/tests/unit/api/test_wiki_router.py`:

```python
from __future__ import annotations

from m_flow.api.v1.wiki import get_wiki_router


def test_wiki_router_exposes_expected_routes():
    router = get_wiki_router()
    paths = {route.path for route in router.routes}

    assert "/ingest" in paths
    assert "/ingest/upload" in paths
    assert "/collections/{collection_id}" in paths
    assert "/collections/{collection_id}/pages" in paths
    assert "/pages/{page_id}" in paths
    assert "/collections/{collection_id}/upgrade" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/api/test_wiki_router.py -q
```

Expected: FAIL because `m_flow.api.v1.wiki` does not exist.

- [ ] **Step 3: Implement router skeleton**

Create `m_flow/api/v1/wiki/routers/get_wiki_router.py`:

```python
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field


class WikiIngestRequest(BaseModel):
    content: str
    dataset_name: Optional[str] = None
    upgrade_after_ingest: bool = False


class WikiCollectionResponse(BaseModel):
    id: str
    dataset_id: str
    title: str
    status: str


def _auth():
    from m_flow.auth.methods import get_authenticated_user

    return get_authenticated_user


def get_wiki_router() -> APIRouter:
    router = APIRouter()

    @router.post("/ingest")
    async def ingest_text(request: WikiIngestRequest, user=Depends(_auth())):
        from m_flow.wiki.service import create_wiki_from_text

        result = await create_wiki_from_text(
            content=request.content,
            dataset_name=request.dataset_name or "main_dataset",
            user=user,
            add_func=None,
            session_factory=None,
            upgrade_after_ingest=request.upgrade_after_ingest,
        )
        return {
            "id": str(result.collection.id),
            "dataset_id": str(result.collection.dataset_id),
            "title": result.collection.title,
            "status": result.collection.status,
        }

    @router.post("/ingest/upload")
    async def ingest_upload(
        data: list[UploadFile] = File(...),
        datasetName: Optional[str] = Form(default=None),
        upgrade_after_ingest: bool = Form(default=False),
        user=Depends(_auth()),
    ):
        content_parts = [(await item.read()).decode("utf-8", errors="ignore") for item in data]
        from m_flow.wiki.service import create_wiki_from_text

        result = await create_wiki_from_text(
            content="\n\n".join(content_parts),
            dataset_name=datasetName or "main_dataset",
            user=user,
            add_func=None,
            session_factory=None,
            upgrade_after_ingest=upgrade_after_ingest,
        )
        return {
            "id": str(result.collection.id),
            "dataset_id": str(result.collection.dataset_id),
            "title": result.collection.title,
            "status": result.collection.status,
        }

    @router.get("/collections/{collection_id}")
    async def get_collection(collection_id: UUID, user=Depends(_auth())):
        return {"id": str(collection_id)}

    @router.get("/collections/{collection_id}/pages")
    async def list_pages(collection_id: UUID, user=Depends(_auth())):
        return {"collection_id": str(collection_id), "pages": []}

    @router.get("/pages/{page_id}")
    async def get_page(page_id: UUID, user=Depends(_auth())):
        return {"id": str(page_id)}

    @router.post("/collections/{collection_id}/upgrade")
    async def upgrade_collection(collection_id: UUID, user=Depends(_auth())):
        return {"id": str(collection_id), "status": "upgrading"}

    return router
```

Create `m_flow/api/v1/wiki/routers/__init__.py`:

```python
from .get_wiki_router import get_wiki_router as get_wiki_router
```

Create `m_flow/api/v1/wiki/__init__.py`:

```python
from .routers import get_wiki_router as get_wiki_router
```

- [ ] **Step 4: Register router in API client**

Modify `m_flow/api/client.py`:

```python
from m_flow.api.v1.wiki import get_wiki_router
```

Add to `route_map`:

```python
(get_wiki_router, "/api/v1/wiki", "wiki"),
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
uv run --with pytest pytest m_flow/tests/unit/api/test_wiki_router.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add m_flow/api/v1/wiki m_flow/api/client.py m_flow/tests/unit/api/test_wiki_router.py
git commit -s -m "feat(wiki): expose wiki ingest api"
```

## Task 7: Wire Wiki Service to Real Persistence and Upgrade

**Files:**
- Modify: `m_flow/wiki/service.py`
- Modify: `m_flow/api/v1/wiki/routers/get_wiki_router.py`
- Test: `m_flow/tests/unit/wiki/test_upgrade.py`

- [ ] **Step 1: Write upgrade test**

Create `m_flow/tests/unit/wiki/test_upgrade.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from m_flow.wiki.service import upgrade_collection_to_mflow


@dataclass
class Collection:
    id: object
    dataset_id: object
    status: str = "ready"


@pytest.mark.asyncio
async def test_upgrade_collection_calls_memorize_in_background():
    calls = []

    async def fake_memorize(**kwargs):
        calls.append(kwargs)
        return {}

    collection = Collection(id=uuid4(), dataset_id=uuid4())
    await upgrade_collection_to_mflow(collection, memorize_func=fake_memorize)

    assert collection.status == "upgrading"
    assert calls[0]["datasets"] == [collection.dataset_id]
    assert calls[0]["run_in_background"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest m_flow/tests/unit/wiki/test_upgrade.py -q
```

Expected: FAIL because `upgrade_collection_to_mflow` does not exist.

- [ ] **Step 3: Implement upgrade helper**

Add to `m_flow/wiki/service.py`:

```python
async def upgrade_collection_to_mflow(collection: Any, memorize_func: Callable[..., Any] | None = None) -> None:
    collection.status = "upgrading"
    if memorize_func is None:
        from m_flow.api.v1.memorize import memorize as memorize_func
    await memorize_func(datasets=[collection.dataset_id], run_in_background=True)
```

- [ ] **Step 4: Update router upgrade endpoint to load collection and call helper**

In `m_flow/api/v1/wiki/routers/get_wiki_router.py`, replace the body of `upgrade_collection` with:

```python
from m_flow.wiki.models import WikiCollection
from m_flow.wiki.service import upgrade_collection_to_mflow
from m_flow.adapters.relational import get_db_adapter

db = get_db_adapter()
async with db.get_async_session() as session:
    collection = await session.get(WikiCollection, collection_id)
    if collection is None:
        return {"id": str(collection_id), "status": "not_found"}
    await upgrade_collection_to_mflow(collection)
    await session.commit()
    return {"id": str(collection.id), "status": collection.status}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest m_flow/tests/unit/wiki/test_upgrade.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add m_flow/wiki/service.py m_flow/api/v1/wiki/routers/get_wiki_router.py m_flow/tests/unit/wiki/test_upgrade.py
git commit -s -m "feat(wiki): support deep memory upgrade"
```

## Task 8: Add Frontend API Types and Client Methods

**Files:**
- Modify: `m_flow-frontend/src/types/index.ts`
- Modify: `m_flow-frontend/src/lib/api/client.ts`
- Test: `m_flow-frontend/src/lib/api/client.test.ts` if existing test setup supports it; otherwise use TypeScript build.

- [ ] **Step 1: Add TypeScript types**

Modify `m_flow-frontend/src/types/index.ts`:

```ts
export type ImportProcessingMode = "wiki" | "mflow" | "wiki_then_mflow";

export interface WikiIngestTextRequest {
  content: string;
  dataset_name?: string;
  upgrade_after_ingest?: boolean;
}

export interface WikiIngestUploadOptions {
  datasetName?: string;
  upgradeAfterIngest?: boolean;
}

export interface WikiCollectionResponse {
  id: string;
  dataset_id: string;
  title: string;
  status: "processing" | "ready" | "failed" | "upgrading" | "upgraded";
}
```

- [ ] **Step 2: Add API client methods**

Modify `m_flow-frontend/src/lib/api/client.ts`:

```ts
async ingestWikiText(request: WikiIngestTextRequest): Promise<WikiCollectionResponse> {
  return this.request<WikiCollectionResponse>("/api/v1/wiki/ingest", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

async ingestWikiFiles(files: File[], options: WikiIngestUploadOptions = {}): Promise<WikiCollectionResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("data", file));
  if (options.datasetName) {
    formData.append("datasetName", options.datasetName);
  }
  if (options.upgradeAfterIngest !== undefined) {
    formData.append("upgrade_after_ingest", String(options.upgradeAfterIngest));
  }
  const headers: HeadersInit = {};
  if (this.token) {
    headers["Authorization"] = `Bearer ${this.token}`;
  }
  const response = await fetch(`${this.baseUrl}/api/v1/wiki/ingest/upload`, {
    method: "POST",
    body: formData,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ code: "WIKI_INGEST_FAILED", message: "Wiki ingest failed" }));
    throw ServiceFault.fromResponse(errorData);
  }
  return response.json();
}
```

Add imports for `WikiCollectionResponse`, `WikiIngestTextRequest`, and `WikiIngestUploadOptions`.

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
cd m_flow-frontend
pnpm exec tsc --noEmit
```

Expected: PASS, or only pre-existing unrelated errors listed separately.

- [ ] **Step 4: Commit**

```bash
git add m_flow-frontend/src/types/index.ts m_flow-frontend/src/lib/api/client.ts
git commit -s -m "feat(frontend): add wiki ingest api client"
```

## Task 9: Add Frontend Processing Mode Selector

**Files:**
- Modify: `m_flow-frontend/src/components/upload/FileUpload.tsx`
- Test: run frontend typecheck/build.

- [ ] **Step 1: Add state for processing mode**

In `FileUpload.tsx`, add:

```tsx
const [processingMode, setProcessingMode] = useState<ImportProcessingMode>("wiki");
```

Import `ImportProcessingMode` from `@/types`.

- [ ] **Step 2: Add selector UI near ingestion options**

Add a compact segmented/select control:

```tsx
<div className="space-y-2">
  <label className="text-sm font-medium text-zinc-200">Processing mode</label>
  <select
    value={processingMode}
    onChange={(event) => setProcessingMode(event.target.value as ImportProcessingMode)}
    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
  >
    <option value="wiki">Wiki 快速模式</option>
    <option value="mflow">M-flow 精细记忆</option>
    <option value="wiki_then_mflow">Wiki + 后台精细记忆</option>
  </select>
  <p className="text-xs text-zinc-500">
    Wiki 模式更快、更省；M-flow 精细记忆更慢，但会构建更丰富的图谱关系。
  </p>
</div>
```

- [ ] **Step 3: Route submit logic by mode**

In the upload submit path:

```tsx
if (processingMode === "wiki" || processingMode === "wiki_then_mflow") {
  const response = await apiClient.ingestWikiFiles(pendingFiles.map((item) => item.file), {
    datasetName,
    upgradeAfterIngest: processingMode === "wiki_then_mflow",
  });
  toast.success(`Wiki generated: ${response.title}`);
  return;
}
```

Keep existing `ingestFiles` behavior for `processingMode === "mflow"`.

- [ ] **Step 4: Run frontend checks**

Run:

```bash
cd m_flow-frontend
pnpm lint
pnpm build
```

Expected: PASS, or document unrelated pre-existing failures.

- [ ] **Step 5: Commit**

```bash
git add m_flow-frontend/src/components/upload/FileUpload.tsx
git commit -s -m "feat(frontend): add wiki import mode"
```

## Task 10: Verification Pass

**Files:**
- No new files unless fixing defects found by verification.

- [ ] **Step 1: Run backend Wiki tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest m_flow/tests/unit/wiki m_flow/tests/unit/api/test_wiki_router.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused compile check**

Run:

```bash
.venv/Scripts/python.exe -m compileall -q m_flow/wiki m_flow/api/v1/wiki
```

Expected: exit code 0.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd m_flow-frontend
pnpm lint
pnpm build
```

Expected: PASS, or document unrelated pre-existing failures.

- [ ] **Step 4: Verify disk output manually with a small sample**

Run a local API or service-level smoke script that calls `create_wiki_from_text()` with a temporary storage root. Confirm:

```text
<temp>/wiki/<collection_id>/index.md exists
<temp>/wiki/<collection_id>/summary.md exists
database metadata does not contain Markdown body content
```

- [ ] **Step 5: Commit fixes if needed**

```bash
git add <fixed-files>
git commit -s -m "fix(wiki): address verification findings"
```

## Self-Review Notes

- Spec coverage: backend models, disk Markdown storage, separate API module, lightweight search, upgrade hook, frontend mode selection, tests, and phased rollout are covered.
- Intentional v1 limit: real LLM concept extraction and vector indexing are not required for the first shippable vertical slice. `generator.py` starts deterministic so the storage/API path is testable; LLM-backed page generation can replace internals later without changing router contracts.
- No Markdown page body is stored in SQL. `WikiPage` uses `file_uri`, hashes, type, title, and `excerpt`.
