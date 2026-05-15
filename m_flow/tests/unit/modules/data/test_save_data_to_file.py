from __future__ import annotations

import os
import tempfile

import pytest

from m_flow.ingestion.core import save_data_to_file
from m_flow.shared.files.storage.config import file_storage_config


@pytest.mark.asyncio
async def test_save_binary_upload_uses_filename_hint_for_storage_name(tmp_path):
    token = file_storage_config.set({"data_root_directory": str(tmp_path)})
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as upload_file:
            temp_path = upload_file.name
            upload_file.write(b"%PDF-1.4\nexample")

        with open(temp_path, "rb") as upload_file:
            stored_path = await save_data_to_file(upload_file, filename="《赢战新周期》.（审校）pdf.pdf")

        assert stored_path.endswith("《赢战新周期》.（审校）pdf.pdf")
        assert stored_path != f"file://{temp_path}"
        assert (tmp_path / "《赢战新周期》.（审校）pdf.pdf").read_bytes() == b"%PDF-1.4\nexample"
    finally:
        file_storage_config.reset(token)
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
