from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)          # UUID
    status: Mapped[str] = mapped_column(String, default="pending")      # pending | running | completed | failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    resources_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_records_count: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("job_runs.id"), index=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)        # Azure full resource ID
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, index=True)
    resource_group: Mapped[str] = mapped_column(String, index=True)
    subscription_id: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str | None] = mapped_column(String, nullable=True)


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("job_runs.id"), index=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)
    resource_name: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    resource_group: Mapped[str] = mapped_column(String)
    resource_location: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str] = mapped_column(String)
    service_name: Mapped[str | None] = mapped_column(String, nullable=True)
    service_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String, default="USD")


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("job_runs.id"), index=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)
    metric_name: Mapped[str] = mapped_column(String)
    avg_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_days: Mapped[int] = mapped_column(Integer, default=30)


class OrphanFinding(Base):
    __tablename__ = "orphan_findings"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # UUID
    run_id: Mapped[str] = mapped_column(String, ForeignKey("job_runs.id"), index=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)
    resource_name: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String, index=True)
    resource_group: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    finding_type: Mapped[str] = mapped_column(String, index=True)        # idle_vm | orphan_disk | cold_storage | …
    severity: Mapped[str] = mapped_column(String, default="medium")      # high | medium | low
    reason: Mapped[str] = mapped_column(Text)
    estimated_monthly_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tag_status: Mapped[str] = mapped_column(String, default="not_tagged") # tagged | not_tagged
    script_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemediationScript(Base):
    __tablename__ = "remediation_scripts"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # UUID
    run_id: Mapped[str] = mapped_column(String, ForeignKey("job_runs.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    script_type: Mapped[str] = mapped_column(String, default="tagging")   # tagging | deletion
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    blob_path: Mapped[str | None] = mapped_column(String, nullable=True)  # path in exports container
