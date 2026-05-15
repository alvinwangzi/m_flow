"""Playground memory retriever — search long-term memories for in-frame persons."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from m_flow.shared.logging_utils import get_logger

_log = get_logger(__name__)


@dataclass
class RetrievalResult:
    context: str = ""
    dataset_sources: list[dict] = field(default_factory=list)
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
