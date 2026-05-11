"""Unit tests for GET /api/v1/dashboard/summary."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from api.models import JobRun, Resource, OrphanFinding, RemediationScript


class TestDashboardSummary:
    def test_no_runs_returns_empty_summary(self, client):
        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_findings"] == 0
        assert data["total_waste_usd"] == 0.0
        assert data["script_ready"] is False

    def test_with_completed_run_returns_kpis(self, client, db_session):
        run_id = str(uuid.uuid4())
        job = JobRun(
            id=run_id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            resources_count=10,
            cost_records_count=5,
            findings_count=2,
        )
        db_session.add(job)

        finding = OrphanFinding(
            id=str(uuid.uuid4()),
            run_id=run_id,
            resource_id="/sub/rg/vm1",
            resource_name="vm1",
            resource_type="microsoft.compute/virtualmachines",
            resource_group="rg1",
            location="eastus",
            finding_type="idle_vm",
            severity="high",
            reason="CPU low",
            estimated_monthly_cost_usd=120.50,
            detected_at=datetime.now(timezone.utc),
        )
        db_session.add(finding)
        db_session.commit()

        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_run_status"] == "completed"
        assert data["total_findings"] == 1
        assert data["total_waste_usd"] == pytest.approx(120.50, abs=0.01)
        assert data["script_ready"] is False

    def test_script_ready_true_when_scripts_exist(self, client, db_session):
        run_id = str(uuid.uuid4())
        job = JobRun(
            id=run_id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            resources_count=5,
            cost_records_count=5,
            findings_count=1,
        )
        db_session.add(job)
        script = RemediationScript(
            id=str(uuid.uuid4()),
            run_id=run_id,
            filename="tagging_abc_20250101.ps1",
            script_type="tagging",
            resource_count=1,
            generated_at=datetime.now(timezone.utc),
            blob_path="scripts/run1/tagging.ps1",
        )
        db_session.add(script)
        db_session.commit()

        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        assert resp.json()["script_ready"] is True

    def test_findings_by_type_aggregated(self, client, db_session):
        run_id = str(uuid.uuid4())
        db_session.add(JobRun(
            id=run_id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            resources_count=5,
            cost_records_count=5,
            findings_count=3,
        ))
        for i, ft in enumerate(["idle_vm", "idle_vm", "orphan_disk"]):
            db_session.add(OrphanFinding(
                id=str(uuid.uuid4()),
                run_id=run_id,
                resource_id=f"/sub/rg/res{i}",
                resource_name=f"res{i}",
                resource_type="test",
                resource_group="rg1",
                location="eastus",
                finding_type=ft,
                severity="high",
                reason="test",
                estimated_monthly_cost_usd=50.0,
                detected_at=datetime.now(timezone.utc),
            ))
        db_session.commit()

        resp = client.get("/api/v1/dashboard/summary")
        data = resp.json()
        by_type = {r["finding_type"]: r for r in data["findings_by_type"]}
        assert by_type["idle_vm"]["count"] == 2
        assert by_type["orphan_disk"]["count"] == 1


import pytest
