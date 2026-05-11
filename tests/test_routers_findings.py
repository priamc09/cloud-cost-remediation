"""Unit tests for GET /api/v1/findings/."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

from api.models import JobRun, OrphanFinding


def _add_run(db, run_id=None):
    rid = run_id or str(uuid.uuid4())
    job = JobRun(
        id=rid,
        status="completed",
        started_at=datetime.now(timezone.utc),
        resources_count=5,
        cost_records_count=5,
        findings_count=1,
    )
    db.add(job)
    db.commit()
    return rid


def _add_finding(db, run_id, finding_type="idle_vm", resource_type="microsoft.compute/virtualmachines"):
    f = OrphanFinding(
        id=str(uuid.uuid4()),
        run_id=run_id,
        resource_id="/sub/rg/vm1",
        resource_name="vm1",
        resource_type=resource_type,
        resource_group="rg1",
        location="eastus",
        finding_type=finding_type,
        severity="high",
        reason="CPU low",
        estimated_monthly_cost_usd=100.0,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(f)
    db.commit()
    return f


class TestFindingsRouter:
    def test_no_runs_returns_empty(self, client):
        resp = client.get("/api/v1/findings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["total_estimated_waste_usd"] == 0.0

    def test_returns_findings_for_latest_run(self, client, db_session):
        run_id = _add_run(db_session)
        _add_finding(db_session, run_id)

        resp = client.get("/api/v1/findings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["finding_type"] == "idle_vm"
        assert data["total_estimated_waste_usd"] == pytest.approx(100.0)

    def test_filter_by_resource_type(self, client, db_session):
        run_id = _add_run(db_session)
        _add_finding(db_session, run_id, resource_type="microsoft.compute/virtualmachines")
        _add_finding(db_session, run_id, resource_type="microsoft.sql/servers/databases")

        resp = client.get("/api/v1/findings/?resource_type=sql")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "sql" in data["items"][0]["resource_type"].lower()

    def test_only_latest_run_findings_returned(self, client, db_session):
        old_run_id = _add_run(db_session)
        _add_finding(db_session, old_run_id)

        new_run_id = _add_run(db_session)
        _add_finding(db_session, new_run_id, finding_type="orphan_disk")

        resp = client.get("/api/v1/findings/")
        data = resp.json()
        # Only findings from newest run
        assert data["total"] == 1
        assert data["items"][0]["finding_type"] == "orphan_disk"

    def test_total_waste_sum(self, client, db_session):
        run_id = _add_run(db_session)
        for cost in [50.0, 75.0, 25.0]:
            f = OrphanFinding(
                id=str(uuid.uuid4()),
                run_id=run_id,
                resource_id=f"/sub/rg/vm{cost}",
                resource_name="vm",
                resource_type="microsoft.compute/virtualmachines",
                resource_group="rg1",
                location="eastus",
                finding_type="idle_vm",
                severity="high",
                reason="test",
                estimated_monthly_cost_usd=cost,
                detected_at=datetime.now(timezone.utc),
            )
            db_session.add(f)
        db_session.commit()

        resp = client.get("/api/v1/findings/")
        data = resp.json()
        assert data["total_estimated_waste_usd"] == pytest.approx(150.0)
