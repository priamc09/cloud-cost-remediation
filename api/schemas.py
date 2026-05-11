"""
Pydantic v2 response schemas.

Inheritance hierarchy
─────────────────────
BaseOut                  – shared model_config for all ORM-backed schemas
  ├─ JobRunOut
  ├─ ResourceOut
  ├─ CostRecordOut
  ├─ OrphanFindingOut
  └─ ScriptOut

BaseListOut[T]           – generic paginated wrapper (total + items)
  ├─ ResourceListOut
  ├─ CostListOut
  └─ FindingsListOut

FindingSummary           – embedded in DashboardSummaryOut
DashboardSummaryOut      – top-level dashboard payload
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

# ── Shared base ───────────────────────────────────────────────────────────────

class BaseOut(BaseModel):
    """Common config for all schemas backed by SQLAlchemy ORM rows."""
    model_config = ConfigDict(from_attributes=True)


# ── Generic list wrapper ──────────────────────────────────────────────────────

T = TypeVar("T", bound=BaseOut)


class BaseListOut(BaseModel, Generic[T]):
    """Paginated list envelope – all list endpoints inherit from this."""
    total: int
    items: list[T]


# ── JobRun ────────────────────────────────────────────────────────────────────

class JobRunOut(BaseOut):
    id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    resources_count: int = 0
    cost_records_count: int = 0
    findings_count: int = 0


# ── Resource ──────────────────────────────────────────────────────────────────

class ResourceOut(BaseOut):
    id: int
    run_id: str
    resource_id: str
    name: str
    type: str
    resource_group: str
    subscription_id: str
    location: str
    tags: dict[str, Any] | None = None
    sku: str | None = None
    kind: str | None = None


class ResourceListOut(BaseListOut[ResourceOut]):
    pass


# ── CostRecord ────────────────────────────────────────────────────────────────

class CostRecordOut(BaseOut):
    id: int
    run_id: str
    resource_id: str
    resource_name: str
    resource_type: str
    resource_group: str
    resource_location: str | None = None
    subscription_id: str
    service_name: str | None = None
    cost_usd: float
    currency: str


class CostListOut(BaseListOut[CostRecordOut]):
    total_cost_usd: float = 0.0


# ── OrphanFinding ─────────────────────────────────────────────────────────────

class OrphanFindingOut(BaseOut):
    id: str
    run_id: str
    resource_id: str
    resource_name: str
    resource_type: str
    resource_group: str
    location: str | None = None
    finding_type: str
    severity: str
    reason: str
    estimated_monthly_cost_usd: float
    tag_status: str
    script_generated: bool
    detected_at: datetime


class FindingsListOut(BaseListOut[OrphanFindingOut]):
    total_estimated_waste_usd: float = 0.0


# ── RemediationScript ─────────────────────────────────────────────────────────

class ScriptOut(BaseOut):
    id: str
    run_id: str
    filename: str
    script_type: str          # tagging | deletion
    resource_count: int
    generated_at: datetime
    blob_path: str | None = None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class FindingSummary(BaseModel):
    finding_type: str
    count: int
    total_waste_usd: float


class DashboardSummaryOut(BaseModel):
    last_run_id: str | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    total_resources: int = 0
    total_findings: int = 0
    total_waste_usd: float = 0.0
    findings_by_type: list[FindingSummary] = []
    script_ready: bool = False