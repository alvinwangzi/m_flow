"""Playground memory retriever — search long-term memories and wiki for in-frame persons."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from m_flow.shared.logging_utils import get_logger

_log = get_logger(__name__)


@dataclass
class RetrievalResult:
    context: str = ""
    dataset_sources: list[dict] = field(default_factory=list)
    wiki_sources: list[dict] = field(default_factory=list)
    empty: bool = True


def _flatten_context_fragment(fragment) -> str:
    """Normalize nested search payloads into plain context text."""
    if fragment is None:
        return ""
    if isinstance(fragment, str):
        return fragment
    if isinstance(fragment, dict):
        parts = [_flatten_context_fragment(value) for value in fragment.values()]
        return "\n---\n".join(part for part in parts if part)
    if isinstance(fragment, list):
        parts = [_flatten_context_fragment(value) for value in fragment]
        return "\n---\n".join(part for part in parts if part)
    return str(fragment)


async def retrieve_memories(
    query: str,
    dataset_ids: list[str],
    user=None,
) -> RetrievalResult:
    """Search M-Flow long-term memory across the given datasets.

    Uses EPISODIC mode — pure vector/graph retrieval, no LLM involved.
    The retrieved context is later injected into the Playground's own LLM call.
    """
    _log.info(
        "Playground memory retrieval start",
        extra={
            "query": query[:200],
            "dataset_ids": dataset_ids,
            "dataset_count": len(dataset_ids),
        },
    )

    if not dataset_ids or not query.strip():
        _log.info("Playground memory retrieval skipped", extra={"reason": "empty_query_or_dataset_ids"})
        return RetrievalResult()

    try:
        from m_flow import search as m_flow_search, RecallMode

        uuids = [UUID(did) for did in dataset_ids]

        result = await m_flow_search(
            query_text=query,
            query_type=RecallMode.EPISODIC,
            dataset_ids=uuids,
            user=user,
            top_k=5,
            only_context=True,
        )

        context_text = ""
        sources: list[dict] = []

        if isinstance(result, list):
            parts = []
            for sr in result:
                if isinstance(sr, dict):
                    sr_ctx = _flatten_context_fragment(sr.get("search_result") or sr.get("context"))
                    ds_name = sr.get("dataset_name", "")
                    ds_id = sr.get("dataset_id", "")
                else:
                    sr_ctx = _flatten_context_fragment(
                        getattr(sr, "search_result", None) or getattr(sr, "context", None)
                    )
                    ds_name = getattr(sr, "dataset_name", "")
                    ds_id = getattr(sr, "dataset_id", "")
                if sr_ctx:
                    parts.append(sr_ctx)
                if ds_name:
                    sources.append({"dataset_id": str(ds_id) if ds_id else "", "dataset_name": ds_name})
            context_text = "\n---\n".join(parts)
        elif isinstance(result, dict):
            context_text = _flatten_context_fragment(result.get("search_result") or result.get("context"))
        elif hasattr(result, "context"):
            ctx = result.context
            if isinstance(ctx, dict):
                context_text = _flatten_context_fragment(ctx)
            else:
                context_text = _flatten_context_fragment(ctx)

        if not context_text.strip():
            _log.info("Playground memory retrieval empty", extra={"dataset_ids": dataset_ids})
            return RetrievalResult()

        _log.info(
            "Playground memory retrieval success",
            extra={
                "dataset_ids": dataset_ids,
                "source_datasets": sources,
                "context_length": len(context_text),
            },
        )
        return RetrievalResult(
            context=context_text,
            dataset_sources=sources,
            empty=False,
        )

    except Exception as e:
        _log.warning(f"Memory retrieval failed (non-fatal): {e}")
        return RetrievalResult()


async def retrieve_wiki_context(
    query: str,
    user=None,
    max_results: int = 5,
    max_excerpt_chars: int = 800,
) -> RetrievalResult:
    """Search Wiki pages for content matching the query.

    Searches across all wiki collections owned by the user, looking at
    page titles, excerpts, and full content. Returns formatted context
    that can be merged with M-flow memory results.
    """
    if not query.strip():
        return RetrievalResult()

    try:
        from m_flow.adapters.relational import get_db_adapter
        from m_flow.wiki.models import WikiCollection, WikiPage
        from sqlalchemy import select, or_

        db = get_db_adapter()
        async with db.get_async_session() as session:
            # Find user's wiki collections
            stmt = select(WikiCollection).where(
                WikiCollection.status == "ready",
                WikiCollection.owner_id == user.id if user else True,
            )
            result = await session.execute(stmt)
            collections = result.scalars().all()

            if not collections:
                return RetrievalResult()

            collection_ids = [c.id for c in collections]

            # Search wiki pages by title, excerpt, or content
            needle = query.lower()
            stmt = select(WikiPage).where(
                WikiPage.collection_id.in_(collection_ids)
            )
            result = await session.execute(stmt)
            all_pages = result.scalars().all()

            matched: list[dict] = []
            for page in all_pages:
                # Check title and excerpt first (fast)
                score = 0
                title_lower = (page.title or "").lower()
                excerpt_lower = (page.excerpt or "").lower()

                if needle in title_lower:
                    score += 10
                if needle in excerpt_lower:
                    score += 5

                # Check full content
                content = ""
                try:
                    file_path = Path(page.file_uri.replace("file://", "", 1))
                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        if needle in content.lower():
                            score += 3
                except (OSError, UnicodeDecodeError):
                    pass

                if score > 0:
                    excerpt_text = content[:max_excerpt_chars] if content else (page.excerpt or "")
                    matched.append({
                        "title": page.title or "Untitled",
                        "excerpt": excerpt_text.strip(),
                        "collection_id": str(page.collection_id),
                        "score": score,
                    })

            # Sort by score and take top results
            matched.sort(key=lambda x: x["score"], reverse=True)
            matched = matched[:max_results]

            if not matched:
                _log.info("Wiki search: no matches", extra={"query": query[:100]})
                return RetrievalResult()

            # Build context from matched pages
            parts = []
            wiki_sources = []
            for m in matched:
                parts.append(f"[Wiki: {m['title']}]\n{m['excerpt']}")
                wiki_sources.append({
                    "collection_id": m["collection_id"],
                    "title": m["title"],
                    "excerpt": m["excerpt"],
                })

            context_text = "\n\n---\n\n".join(parts)

            _log.info(
                "Wiki search success",
                extra={
                    "query": query[:100],
                    "matches": len(matched),
                    "collections": len(collections),
                },
            )

            return RetrievalResult(
                context=context_text,
                wiki_sources=wiki_sources,
                empty=False,
            )

    except Exception as e:
        _log.warning(f"Wiki retrieval failed (non-fatal): {e}")
        return RetrievalResult()
