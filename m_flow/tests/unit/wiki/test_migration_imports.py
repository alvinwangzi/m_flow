"""
Wiki Migration Import Tests

Tests that verify the wiki migration file exists and has correct structure.
"""

from __future__ import annotations

from pathlib import Path


def test_wiki_migration_exists_and_creates_tables():
    """Verify migration file exists and contains expected tables."""
    migration_files = list(Path("alembic/versions").glob("*_add_wiki_tables.py"))
    assert migration_files, "Expected add_wiki_tables migration"

    content = migration_files[0].read_text(encoding="utf-8")
    assert "wiki_collections" in content
    assert "wiki_pages" in content
    assert "file_uri" in content

    # Content should NOT be stored as a column (it's on disk)
    assert 'Column("content"' not in content
    assert 'sa.Column("content"' not in content


def test_wiki_migration_has_correct_revision_chain():
    """Verify migration has correct revision chain."""
    migration_file = Path("alembic/versions/20260518_add_wiki_tables.py")
    if migration_file.exists():
        content = migration_file.read_text(encoding="utf-8")
        assert 'down_revision: str = "92b3293baa66"' in content
        assert 'revision: str = "20260518_wiki"' in content