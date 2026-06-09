"""
Wiki Disk-Backed Storage

Handles reading and writing of wiki markdown files to disk.
Content is stored outside the database for efficiency.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from m_flow.shared.files.storage import get_storage_config


class WikiStorage:
    """
    Disk-backed storage for generated Wiki Markdown pages.

    Pages are stored at: <data_root_directory>/wiki/<collection_id>/<page_path>
    """

    def __init__(self, root_dir: str | None = None) -> None:
        """Initialize storage with optional root directory override."""
        cfg = get_storage_config()
        self.root_dir = Path(root_dir or cfg["data_root_directory"]).resolve()

    def collection_dir(self, collection_id: UUID) -> Path:
        """Get the root directory for a collection."""
        return self.root_dir / "wiki" / str(collection_id)

    def resolve_page_path(self, collection_id: UUID, relative_path: str) -> Path:
        """
        Resolve a relative page path with security checks.

        Raises:
            ValueError: If path is absolute or contains traversal attempts.
        """
        rel = Path(relative_path.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe wiki page path: {relative_path}")

        target = (self.collection_dir(collection_id) / rel).resolve()
        base = self.collection_dir(collection_id).resolve()

        # Ensure target is within base directory
        if os.path.commonpath([str(base), str(target)]) != str(base):
            raise ValueError(f"Unsafe wiki page path: {relative_path}")

        return target

    def write_page(self, collection_id: UUID, relative_path: str, content: str) -> str:
        """
        Write markdown content to disk.

        Args:
            collection_id: Collection UUID.
            relative_path: Relative path within collection (e.g., "chapters/intro.md").
            content: Markdown content to write.

        Returns:
            Absolute file:// URI to the written file.
        """
        target = self.resolve_page_path(collection_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return "file://" + str(target)

    def write_binary(self, collection_id: UUID, relative_path: str, data: bytes) -> str:
        """
        Write binary data to disk (e.g., original .docx/.pdf files).

        Args:
            collection_id: Collection UUID.
            relative_path: Relative path within collection.
            data: Raw binary content.

        Returns:
            Absolute file:// URI to the written file.
        """
        target = self.resolve_page_path(collection_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return "file://" + str(target)

    def read_page(self, collection_id: UUID, relative_path: str) -> str:
        """Read markdown content from disk."""
        return self.resolve_page_path(collection_id, relative_path).read_text(encoding="utf-8")

    def page_exists(self, collection_id: UUID, relative_path: str) -> bool:
        """Check if a page exists on disk."""
        try:
            path = self.resolve_page_path(collection_id, relative_path)
            return path.exists()
        except ValueError:
            return False

    def delete_page(self, collection_id: UUID, relative_path: str) -> bool:
        """Delete a page from disk. Returns True if deleted."""
        try:
            path = self.resolve_page_path(collection_id, relative_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except ValueError:
            return False

    def delete_collection(self, collection_id: UUID) -> bool:
        """Delete all pages for a collection. Returns True if deleted."""
        collection_path = self.collection_dir(collection_id)
        if collection_path.exists():
            import shutil
            shutil.rmtree(collection_path)
            return True
        return False