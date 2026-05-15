from __future__ import annotations

from m_flow.api.v1.playground.routers.get_playground_router import _build_effective_dataset_ids


def test_selected_dataset_is_used_as_fallback() -> None:
    result = _build_effective_dataset_ids(
        face_dataset_mapping={},
        registered_ids=[],
        selected_dataset_id="ds-fallback",
    )
    assert result == ["ds-fallback"]


def test_selected_dataset_merges_with_face_linked_datasets() -> None:
    result = _build_effective_dataset_ids(
        face_dataset_mapping={1: ["ds-a", "ds-b"]},
        registered_ids=[1],
        selected_dataset_id="ds-fallback",
    )
    assert result == ["ds-a", "ds-b", "ds-fallback"]


def test_selected_dataset_is_not_duplicated() -> None:
    result = _build_effective_dataset_ids(
        face_dataset_mapping={1: ["ds-a", "ds-b"]},
        registered_ids=[1],
        selected_dataset_id="ds-b",
    )
    assert result == ["ds-a", "ds-b"]
