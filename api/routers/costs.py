"""GET /api/v1/costs/ – latest-run cost records."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import JobRun, CostRecord
from api.schemas import CostListOut, CostRecordOut

router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


@router.get("/", response_model=CostListOut)
def list_costs(db: Session = Depends(get_db)):
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        return CostListOut(total=0, items=[], total_cost_usd=0.0)
    rows = db.query(CostRecord).filter(CostRecord.run_id == latest.id).all()
    return CostListOut(
        total=len(rows),
        items=[CostRecordOut.model_validate(r) for r in rows],
        total_cost_usd=sum(r.cost_usd for r in rows),
    )