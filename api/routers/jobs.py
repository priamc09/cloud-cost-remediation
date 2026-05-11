"""
Jobs router.

POST /api/v1/jobs/extract-all  → trigger pipeline (BackgroundTask), return 202
GET  /api/v1/jobs/{job_id}     → poll status

Class
─────
PipelineRunner(run_id, resource_svc, cost_svc, db_storage)
  All collaborators injected at construction via FastAPI Depends(),
  resolved at request time and passed into the BackgroundTask so the
  runner holds real objects (not closed session refs).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db, SessionLocal
from api.dependencies import (
    get_resource_export_dep,
    get_cost_export_dep,
    get_db_storage_dep,
)
from api.models import JobRun, Resource, CostRecord, OrphanFinding
from api.schemas import JobRunOut
from api.services.resource_export import ResourceExportService
from api.services.cost_export import CostExportService
from api.services.storage import DBContainerService
from api import analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# ── Pipeline runner ───────────────────────────────────────────────────────────

class PipelineRunner:
    """
    Encapsulates the full extract-analyse-persist cycle for one job run.

    All service collaborators are injected via constructor so the class
    is unit-testable without FastAPI infrastructure.
    """

    def __init__(
        self,
        run_id: str,
        resource_svc: ResourceExportService,
        cost_svc: CostExportService,
        db_storage: DBContainerService,
    ) -> None:
        self._run_id = run_id
        self._resource_svc = resource_svc
        self._cost_svc = cost_svc
        self._db_storage = db_storage

    def execute(self) -> None:
        """Run in a BackgroundTask; opens its own DB session."""
        db = SessionLocal()
        pipeline_start = perf_counter()
        logger.info("[run=%s] Pipeline starting", self._run_id[:8])
        try:
            self._set_status(db, "running")

            # 1. Resources
            t = perf_counter()
            logger.info("[run=%s] Step 1/4: Fetching Azure resources…", self._run_id[:8])
            raw_resources = self._resource_svc.fetch_all()
            logger.info("[run=%s] Step 1/4 complete | resources=%d | %.1fs",
                        self._run_id[:8], len(raw_resources), perf_counter() - t)
            db.bulk_insert_mappings(
                Resource,
                [
                    dict(run_id=self._run_id, **{
                        k: r[k] for k in (
                            "resource_id", "name", "type", "resource_group",
                            "subscription_id", "location", "tags", "sku", "kind"
                        )
                    })
                    for r in raw_resources
                ],
            )
            db.flush()

            # 2. Costs
            t = perf_counter()
            logger.info("[run=%s] Step 2/4: Fetching cost data…", self._run_id[:8])
            raw_costs = self._cost_svc.fetch_cost_by_resource()
            logger.info("[run=%s] Step 2/4 complete | cost_records=%d | %.1fs",
                        self._run_id[:8], len(raw_costs), perf_counter() - t)
            db.bulk_insert_mappings(
                CostRecord,
                [
                    dict(run_id=self._run_id, **{
                        k: c[k] for k in (
                            "resource_id", "resource_name", "resource_type",
                            "resource_group", "resource_location", "subscription_id",
                            "service_name", "service_tier", "cost_usd", "currency"
                        )
                    })
                    for c in raw_costs
                ],
            )
            db.flush()

            # 3. Cost map
            cost_map: dict[str, float] = {}
            for c in raw_costs:
                rid = c["resource_id"].lower()
                cost_map[rid] = cost_map.get(rid, 0.0) + c["cost_usd"]
            total_waste = sum(cost_map.values())
            logger.info("[run=%s] Cost map built | unique_resources=%d total_cost_usd=%.2f",
                        self._run_id[:8], len(cost_map), total_waste)

            # 4. Analysis
            t = perf_counter()
            logger.info("[run=%s] Step 3/4: Running analysis across %d resources…",
                        self._run_id[:8], len(raw_resources))
            resource_dicts = [
                {k: r[k] for k in ("resource_id", "name", "type", "resource_group", "location", "kind")}
                for r in raw_resources
            ]
            findings = analysis.run_all(resource_dicts, cost_map)
            estimated_waste = sum(f.estimated_monthly_cost_usd for f in findings)
            logger.info(
                "[run=%s] Step 3/4 complete | findings=%d estimated_waste_usd=%.2f | %.1fs",
                self._run_id[:8], len(findings), estimated_waste, perf_counter() - t,
            )
            db.bulk_insert_mappings(
                OrphanFinding,
                [
                    {
                        "id": str(uuid.uuid4()),
                        "run_id": self._run_id,
                        "resource_id": f.resource_id,
                        "resource_name": f.resource_name,
                        "resource_type": f.resource_type,
                        "resource_group": f.resource_group,
                        "location": f.location,
                        "finding_type": f.finding_type,
                        "severity": f.severity,
                        "reason": f.reason,
                        "estimated_monthly_cost_usd": f.estimated_monthly_cost_usd,
                    }
                    for f in findings
                ],
            )

            # 5. Finalise job record
            t = perf_counter()
            logger.info("[run=%s] Step 4/4: Persisting results…", self._run_id[:8])
            job = db.query(JobRun).filter(JobRun.id == self._run_id).first()
            if job:
                job.resources_count = len(raw_resources)
                job.cost_records_count = len(raw_costs)
                job.findings_count = len(findings)
                job.status = "completed"
                job.completed_at = datetime.utcnow()
            db.commit()
            logger.info("[run=%s] Step 4/4 complete | %.1fs", self._run_id[:8], perf_counter() - t)

            # 6. Persist DB blob
            logger.info("[run=%s] Uploading DB blob…", self._run_id[:8])
            self._db_storage.upload_db()

            elapsed = perf_counter() - pipeline_start
            logger.info(
                "[run=%s] Pipeline COMPLETE | resources=%d costs=%d findings=%d "
                "waste_usd=%.2f | total_time=%.1fs",
                self._run_id[:8], len(raw_resources), len(raw_costs),
                len(findings), estimated_waste, elapsed,
            )

        except Exception as exc:
            elapsed = perf_counter() - pipeline_start
            logger.error(
                "[run=%s] Pipeline FAILED after %.1fs: %s",
                self._run_id[:8], elapsed, exc, exc_info=True,
            )
            db.rollback()
            self._set_status(db, "failed", str(exc))
        finally:
            db.close()

    def _set_status(self, db: Session, status: str, error: str | None = None) -> None:
        job = db.query(JobRun).filter(JobRun.id == self._run_id).first()
        if job:
            job.status = status
            if error:
                job.error_message = error
            if status in ("completed", "failed"):
                job.completed_at = datetime.utcnow()
            db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[JobRunOut])
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    """Return the most recent job runs."""
    rows = db.query(JobRun).order_by(JobRun.started_at.desc()).limit(limit).all()
    return rows


@router.post("/extract-all", response_model=JobRunOut, status_code=202)
def trigger_extract_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    resource_svc: ResourceExportService = Depends(get_resource_export_dep),
    cost_svc: CostExportService = Depends(get_cost_export_dep),
    db_storage: DBContainerService = Depends(get_db_storage_dep),
):
    """Trigger the full pipeline; returns job_id immediately (202 Accepted)."""
    run_id = str(uuid.uuid4())
    job = JobRun(id=run_id, status="pending", started_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    runner = PipelineRunner(run_id, resource_svc, cost_svc, db_storage)
    background_tasks.add_task(runner.execute)
    return job


@router.get("/{job_id}", response_model=JobRunOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Poll job status by job_id."""
    job = db.query(JobRun).filter(JobRun.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job