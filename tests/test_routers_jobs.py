"""Unit tests for jobs router: POST /extract-all, GET /, GET /{id}."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from api.models import JobRun


def _add_job(db, status="completed", findings=3, resources=10):
    job = JobRun(
        id=str(uuid.uuid4()),
        status=status,
        started_at=datetime.now(timezone.utc),
        resources_count=resources,
        cost_records_count=resources,
        findings_count=findings,
    )
    db.add(job)
    db.commit()
    return job


class TestJobsList:
    def test_empty_list(self, client):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_jobs(self, client, db_session):
        _add_job(db_session)
        _add_job(db_session, status="failed")
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_ordered_newest_first(self, client, db_session):
        j1 = _add_job(db_session, status="completed")
        j2 = _add_job(db_session, status="failed")
        resp = client.get("/api/v1/jobs")
        ids = [j["id"] for j in resp.json()]
        # Newest (j2) should be first
        assert ids[0] == j2.id


class TestJobGetById:
    def test_get_by_id_found(self, client, db_session):
        job = _add_job(db_session)
        resp = client.get(f"/api/v1/jobs/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job.id
        assert data["status"] == "completed"
        assert data["findings_count"] == 3

    def test_get_by_id_not_found(self, client):
        resp = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_job_fields_complete(self, client, db_session):
        job = _add_job(db_session, resources=20, findings=5)
        resp = client.get(f"/api/v1/jobs/{job.id}")
        data = resp.json()
        assert data["resources_count"] == 20
        assert data["findings_count"] == 5


class TestTriggerPipeline:
    def test_post_extract_all_returns_202(self, client):
        with patch("api.routers.jobs.PipelineRunner") as MockRunner:
            mock_instance = MagicMock()
            MockRunner.return_value = mock_instance
            resp = client.post("/api/v1/jobs/extract-all")
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"

    def test_post_extract_all_creates_job_run(self, client, db_session):
        with patch("api.routers.jobs.PipelineRunner") as MockRunner:
            mock_instance = MagicMock()
            MockRunner.return_value = mock_instance
            resp = client.post("/api/v1/jobs/extract-all")

        assert resp.status_code == 202
        job_id = resp.json()["id"]
        job = db_session.query(JobRun).filter(JobRun.id == job_id).first()
        assert job is not None
        assert job.status == "pending"

    def test_health_endpoint(self, client, db_session):
        _add_job(db_session, status="completed")
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
