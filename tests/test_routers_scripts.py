"""Unit tests for scripts router: POST /generate, GET /download-all."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from api.models import JobRun, OrphanFinding, RemediationScript


def _add_run(db):
    rid = str(uuid.uuid4())
    db.add(JobRun(
        id=rid,
        status="completed",
        started_at=datetime.now(timezone.utc),
        resources_count=5,
        cost_records_count=5,
        findings_count=2,
    ))
    db.commit()
    return rid


def _add_finding(db, run_id, idx=0):
    f = OrphanFinding(
        id=str(uuid.uuid4()),
        run_id=run_id,
        resource_id=f"/sub/rg/vm{idx}",
        resource_name=f"vm{idx}",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg1",
        location="eastus",
        finding_type="idle_vm",
        severity="high",
        reason="CPU < 5%",
        estimated_monthly_cost_usd=100.0,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(f)
    db.commit()
    return f


def _add_script(db, run_id, script_type="tagging"):
    s = RemediationScript(
        id=str(uuid.uuid4()),
        run_id=run_id,
        filename=f"{script_type}_abcd_20250101.ps1",
        script_type=script_type,
        resource_count=2,
        generated_at=datetime.now(timezone.utc),
        blob_path=f"scripts/{run_id}/{script_type}.ps1",
    )
    db.add(s)
    db.commit()
    return s


class TestGenerateScripts:
    def test_no_run_returns_404(self, client):
        resp = client.post("/api/v1/scripts/generate")
        assert resp.status_code == 404

    def test_no_findings_returns_404(self, client, db_session):
        _add_run(db_session)
        resp = client.post("/api/v1/scripts/generate")
        assert resp.status_code == 404

    def test_generate_creates_two_scripts(self, client, db_session):
        run_id = _add_run(db_session)
        _add_finding(db_session, run_id, idx=0)
        _add_finding(db_session, run_id, idx=1)

        mock_exports = MagicMock()
        mock_exports.upload_export.return_value = "scripts/run1/tagging.ps1"

        with patch("api.routers.scripts.get_exports_storage_dep",
                   return_value=lambda: mock_exports), \
             patch("api.routers.scripts.ScriptBuilder") as MockBuilder:
            mock_builder_instance = MagicMock()
            tagging_rec = {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "filename": "tagging_abc_20250101.ps1",
                "script_type": "tagging",
                "resource_count": 2,
                "generated_at": datetime.now(timezone.utc),
                "blob_path": f"scripts/{run_id}/tagging.ps1",
            }
            deletion_rec = {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "filename": "deletion_abc_20250101.ps1",
                "script_type": "deletion",
                "resource_count": 2,
                "generated_at": datetime.now(timezone.utc),
                "blob_path": f"scripts/{run_id}/deletion.ps1",
            }
            mock_builder_instance.generate.return_value = (tagging_rec, deletion_rec)
            MockBuilder.return_value = mock_builder_instance

            resp = client.post("/api/v1/scripts/generate")

        # Should return 200 with 2 script records
        assert resp.status_code == 200
        scripts = resp.json()
        assert len(scripts) == 2
        types = {s["script_type"] for s in scripts}
        assert types == {"tagging", "deletion"}


class TestDownloadAllScripts:
    def test_no_run_returns_404(self, client):
        resp = client.get("/api/v1/scripts/download-all")
        assert resp.status_code == 404

    def test_no_scripts_returns_404(self, client, db_session):
        _add_run(db_session)
        resp = client.get("/api/v1/scripts/download-all")
        assert resp.status_code == 404

    def test_download_returns_zip(self, client, db_session):
        run_id = _add_run(db_session)
        _add_script(db_session, run_id, "tagging")
        _add_script(db_session, run_id, "deletion")

        mock_exports = MagicMock()
        mock_exports.get_export_blob_bytes.return_value = b"# PowerShell content"

        with patch("api.routers.scripts.get_exports_storage_dep",
                   return_value=lambda: mock_exports):
            resp = client.get("/api/v1/scripts/download-all")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        # Verify it's a valid zip
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            assert len(zf.namelist()) == 2
