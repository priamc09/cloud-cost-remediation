"""Tests for /api/v1/costs and /api/v1/resources routers."""
from __future__ import annotations
import uuid
from datetime import datetime


def _add_job(db, status="completed"):
    from api.models import JobRun
    job = JobRun(id=str(uuid.uuid4()), status=status, started_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class TestCostsRouter:
    def test_no_runs_returns_empty(self, client):
        resp = client.get("/api/v1/costs/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_cost_records(self, client, db_session):
        from api.models import CostRecord
        job = _add_job(db_session)
        rec = CostRecord(
            run_id=job.id,
            resource_id="/sub/rg/providers/Microsoft.Compute/vm1",
            resource_name="vm1",
            resource_type="microsoft.compute/virtualmachines",
            resource_group="rg1",
            subscription_id="test-sub",
            cost_usd=42.5,
            currency="USD",
        )
        db_session.add(rec)
        db_session.commit()
        resp = client.get("/api/v1/costs/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["cost_usd"] == 42.5


class TestResourcesRouter:
    def test_no_runs_returns_empty(self, client):
        resp = client.get("/api/v1/resources/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_resources(self, client, db_session):
        from api.models import Resource
        job = _add_job(db_session)
        res = Resource(
            run_id=job.id,
            resource_id="/sub/rg/providers/Microsoft.Compute/vm1",
            name="vm1",
            type="microsoft.compute/virtualmachines",
            resource_group="rg1",
            subscription_id="test-sub",
            location="eastus",
        )
        db_session.add(res)
        db_session.commit()
        resp = client.get("/api/v1/resources/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "vm1"
