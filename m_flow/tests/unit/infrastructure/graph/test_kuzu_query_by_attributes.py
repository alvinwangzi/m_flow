from __future__ import annotations

import pytest

from m_flow.adapters.graph.kuzu.adapter import KuzuAdapter


class _FakeKuzuAdapter(KuzuAdapter):
    def __init__(self):
        self.captured = []

    async def query(self, cypher: str, params: dict | None = None):
        self.captured.append((cypher, params or {}))
        if "RETURN n1.id" in cypher:
            return []
        return []


@pytest.mark.asyncio
async def test_query_by_attributes_reads_canonical_name_from_properties_json():
    adapter = _FakeKuzuAdapter()

    await adapter.query_by_attributes([{"type": ["Entity"], "canonical_name": ["alice"]}])

    node_query, params = adapter.captured[0]
    edge_query, edge_params = adapter.captured[1]

    assert "json_extract_string(n.properties, '$.canonical_name') IN $vals_0_canonical_name" in node_query
    assert "n.type IN $vals_0_type" in node_query
    assert "n1.type IN $vals_0_type" in edge_query
    assert (
        "json_extract_string(n1.properties, '$.canonical_name') IN $vals_0_canonical_name" in edge_query
    )
    assert params["vals_0_canonical_name"] == ["alice"]
    assert edge_params["vals_0_canonical_name"] == ["alice"]
