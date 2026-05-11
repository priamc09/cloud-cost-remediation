"""GET /api/v1/findings/ – latest-run findings with optional type filter."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import JobRun, OrphanFinding
from api.schemas import FindingsListOut, OrphanFindingOut

router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


@router.get("/", response_model=FindingsListOut)
def list_findings(
    resource_type: str | None = Query(default=None, description="Filter by ARM resource type"),
    db: Session = Depends(get_db),
):
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        return FindingsListOut(total=0, items=[], total_estimated_waste_usd=0.0)

    q = db.query(OrphanFinding).filter(OrphanFinding.run_id == latest.id)
    if resource_type:
        q = q.filter(OrphanFinding.resource_type.ilike(f"%{resource_type}%"))

    rows = q.all()
    return FindingsListOut(
        total=len(rows),
        items=[OrphanFindingOut.model_validate(r) for r in rows],
        total_estimated_waste_usd=sum(r.estimated_monthly_cost_usd for r in rows),
    )