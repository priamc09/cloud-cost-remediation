"""GET /api/v1/dashboard/summary – single payload for the React SPA."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import JobRun, Resource, OrphanFinding, RemediationScript
from api.schemas import DashboardSummaryOut, FindingSummary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(db: Session = Depends(get_db)):
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        return DashboardSummaryOut()

    run_id = latest.id
    total_resources = db.query(Resource).filter(Resource.run_id == run_id).count()
    findings = db.query(OrphanFinding).filter(OrphanFinding.run_id == run_id).all()
    total_waste = sum(f.estimated_monthly_cost_usd for f in findings)

    type_rows = (
        db.query(
            OrphanFinding.finding_type,
            func.count(OrphanFinding.id).label("cnt"),
            func.sum(OrphanFinding.estimated_monthly_cost_usd).label("waste"),
        )
        .filter(OrphanFinding.run_id == run_id)
        .group_by(OrphanFinding.finding_type)
        .all()
    )
    script_ready = (
        db.query(RemediationScript).filter(RemediationScript.run_id == run_id).count() > 0
    )
    return DashboardSummaryOut(
        last_run_id=run_id,
        last_run_status=latest.status,
        last_run_at=latest.started_at,
        total_resources=total_resources,
        total_findings=len(findings),
        total_waste_usd=total_waste,
        findings_by_type=[
            FindingSummary(finding_type=r.finding_type, count=r.cnt, total_waste_usd=r.waste or 0.0)
            for r in type_rows
        ],
        script_ready=script_ready,
    )