"""Unit tests for DBContainerService and ExportsContainerService."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from azure.core.exceptions import ResourceNotFoundError


# ── DBContainerService ────────────────────────────────────────────────────────

class TestDBContainerService:
    def _make_svc(self, tmp_path):
        """Build a DBContainerService with mocked blob client and KV."""
        with patch("api.services.storage.get_kv_secret", return_value="fake-sas?sv=2023"), \
             patch("api.services.storage.ContainerClient") as MockCC:
            mock_container = MagicMock()
            MockCC.from_container_url.return_value = mock_container

            from api.services.storage import DBContainerService
            svc = DBContainerService.__new__(DBContainerService)
            svc._container_name = "optimizer-db"
            svc._kv_secret_name = "storage-db-sas-token"
            svc._storage_account_url = "https://fake.blob.core.windows.net"
            svc._local_path = tmp_path / "optimizer.db"
            svc._blob_name = "optimizer.db"
            svc._mock_container = mock_container
            return svc, mock_container

    def test_download_db_writes_file(self, tmp_path):
        svc, mock_container = self._make_svc(tmp_path)
        blob_data = b"SQLite format 3"

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = blob_data
        mock_container.get_blob_client.return_value = mock_blob_client

        with patch.object(svc, "_client", return_value=mock_container):
            svc.download_bytes = MagicMock(return_value=blob_data)
            svc.download_db()

        assert svc._local_path.exists()
        assert svc._local_path.read_bytes() == blob_data

    def test_download_db_handles_not_found_gracefully(self, tmp_path):
        """First run — blob doesn't exist yet. Should not raise."""
        svc, _ = self._make_svc(tmp_path)
        svc.download_bytes = MagicMock(side_effect=ResourceNotFoundError("not found"))
        # Should not raise
        svc.download_db()
        assert not svc._local_path.exists()

    def test_upload_db_uploads_file(self, tmp_path):
        svc, _ = self._make_svc(tmp_path)
        # Create local DB
        svc._local_path.write_bytes(b"SQLite format 3")
        svc.upload_file = MagicMock(return_value="optimizer.db")
        svc.upload_db()
        svc.upload_file.assert_called_once_with("optimizer.db", svc._local_path)

    def test_upload_db_skips_if_no_local_file(self, tmp_path):
        svc, _ = self._make_svc(tmp_path)
        svc.upload_file = MagicMock()
        svc.upload_db()
        svc.upload_file.assert_not_called()

    def test_download_db_propagates_unexpected_error(self, tmp_path):
        svc, _ = self._make_svc(tmp_path)
        svc.download_bytes = MagicMock(side_effect=RuntimeError("unexpected"))
        with pytest.raises(RuntimeError):
            svc.download_db()


# ── ExportsContainerService ───────────────────────────────────────────────────

class TestExportsContainerService:
    def _make_svc(self):
        from api.services.storage import ExportsContainerService
        svc = ExportsContainerService.__new__(ExportsContainerService)
        svc._container_name = "optimizer-exports"
        svc._kv_secret_name = "storage-exports-sas-token"
        svc._storage_account_url = "https://fake.blob.core.windows.net"
        return svc

    def test_upload_export_calls_upload_file(self, tmp_path):
        svc = self._make_svc()
        local = tmp_path / "tagging.ps1"
        local.write_text("# script")
        svc.upload_file = MagicMock(return_value="scripts/run1/tagging.ps1")
        result = svc.upload_export("scripts/run1/tagging.ps1", local)
        assert result == "scripts/run1/tagging.ps1"
        svc.upload_file.assert_called_once()

    def test_get_export_blob_bytes_returns_bytes(self):
        svc = self._make_svc()
        svc.download_bytes = MagicMock(return_value=b"# content")
        result = svc.get_export_blob_bytes("scripts/run1/tagging.ps1")
        assert result == b"# content"

    def test_get_export_blob_bytes_raises_not_found(self):
        svc = self._make_svc()
        svc.download_bytes = MagicMock(side_effect=ResourceNotFoundError("not found"))
        with pytest.raises(ResourceNotFoundError):
            svc.get_export_blob_bytes("scripts/run1/tagging.ps1")

    def test_upload_export_propagates_error(self, tmp_path):
        svc = self._make_svc()
        svc.upload_file = MagicMock(side_effect=RuntimeError("upload failed"))
        with pytest.raises(RuntimeError):
            svc.upload_export("scripts/run1/tagging.ps1", tmp_path / "tagging.ps1")
