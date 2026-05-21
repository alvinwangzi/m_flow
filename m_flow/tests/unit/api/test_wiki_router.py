"""
Wiki Router Registration Tests

Tests that verify the wiki router is properly registered.
"""

from __future__ import annotations

from m_flow.api.v1.wiki import get_wiki_router


def test_wiki_router_exposes_expected_routes():
    """Verify wiki router has expected route paths."""
    router = get_wiki_router()
    paths = {route.path for route in router.routes}

    assert "/ingest" in paths
    assert "/ingest/upload" in paths
    assert "/collections/{collection_id}" in paths
    assert "/collections/{collection_id}/pages" in paths
    assert "/pages/{page_id}" in paths
    assert "/collections/{collection_id}/upgrade" in paths


def test_wiki_router_includes_auth_dependency():
    """Verify wiki router endpoints use authentication."""
    router = get_wiki_router()

    for route in router.routes:
        # Each route should have dependencies (auth)
        assert route.dependant.dependencies, f"Route {route.path} missing dependencies"