"""
Wiki Storage Tests

Tests for WikiStorage disk-backed markdown storage.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from m_flow.shared.files.storage.config import file_storage_config
from m_flow.wiki.storage import WikiStorage


def test_wiki_storage_writes_markdown_under_data_root(tmp_path):
    """Verify wiki pages are written under the data root directory."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        file_uri = storage.write_page(collection_id, "chapters/chapter-01.md", "# Chapter\nBody content here")

        expected = tmp_path / "wiki" / str(collection_id) / "chapters" / "chapter-01.md"
        assert expected.read_text(encoding="utf-8") == "# Chapter\nBody content here"
        assert file_uri == "file://" + str(expected)
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_rejects_absolute_paths(tmp_path):
    """WikiStorage should reject absolute paths."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        storage = WikiStorage()
        collection_id = uuid4()

        with pytest.raises(ValueError, match="Unsafe wiki page path"):
            storage.write_page(collection_id, "/etc/passwd", "bad content")
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_rejects_path_traversal(tmp_path):
    """WikiStorage should reject path traversal attempts."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        storage = WikiStorage()
        collection_id = uuid4()

        with pytest.raises(ValueError, match="Unsafe wiki page path"):
            storage.write_page(collection_id, "../escape.md", "bad content")

        with pytest.raises(ValueError, match="Unsafe wiki page path"):
            storage.write_page(collection_id, "foo/../../bar.md", "bad content")
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_read_page(tmp_path):
    """WikiStorage should read back what was written."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        content = "# Test Page\n\nThis is test content."
        storage.write_page(collection_id, "test.md", content)

        read_content = storage.read_page(collection_id, "test.md")
        assert read_content == content
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_page_exists(tmp_path):
    """WikiStorage should correctly report page existence."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        assert not storage.page_exists(collection_id, "test.md")

        storage.write_page(collection_id, "test.md", "# Test")
        assert storage.page_exists(collection_id, "test.md")
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_delete_page(tmp_path):
    """WikiStorage should delete pages correctly."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        storage.write_page(collection_id, "test.md", "# Test")
        assert storage.page_exists(collection_id, "test.md")

        deleted = storage.delete_page(collection_id, "test.md")
        assert deleted is True
        assert not storage.page_exists(collection_id, "test.md")
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_delete_collection(tmp_path):
    """WikiStorage should delete entire collection directory."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        storage.write_page(collection_id, "page1.md", "# Page 1")
        storage.write_page(collection_id, "page2.md", "# Page 2")

        collection_dir = tmp_path / "wiki" / str(collection_id)
        assert collection_dir.exists()

        deleted = storage.delete_collection(collection_id)
        assert deleted is True
        assert not collection_dir.exists()
    finally:
        file_storage_config.reset(token)


def test_wiki_storage_collection_dir(tmp_path):
    """Verify collection directory path construction."""
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    try:
        collection_id = uuid4()
        storage = WikiStorage()

        collection_dir = storage.collection_dir(collection_id)
        expected = tmp_path / "wiki" / str(collection_id)
        assert collection_dir == expected
    finally:
        file_storage_config.reset(token)