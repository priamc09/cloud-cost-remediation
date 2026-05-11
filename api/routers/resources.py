"""GET /api/v1/resources/ – latest-run resources."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import JobRun, Resource
from api.schemas import ResourceListOut, ResourceOut

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


@router.get("/", response_model=ResourceListOut)
def list_resources(db: Session = Depends(get_db)):
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        return ResourceListOut(total=0, items=[])
    rows = db.query(Resource).filter(Resource.run_id == latest.id).all()
    return ResourceListOut(
        total=len(rows),
        items=[ResourceOut.model_validate(r) for r in rows],
    )