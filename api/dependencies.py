"""
Dependency injection wiring for FastAPI.

All service singletons are exposed as FastAPI-compatible dependency
functions using Annotated + Depends so routers declare intent cleanly:

    from api.dependencies import DBStorageDep, ExportsStorageDep, MetricsSvcDep

    @router.post("/...")
    def my_endpoint(
        db:      Session              = Depends(get_db),
        exports: ExportsContainerService = Depends(get_exports_storage_dep),
    ): ...

The factories delegate to the process-wide @lru_cache singletons, so
no object is created more than once per process.  Tests can override
any dependency via app.dependency_overrides.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.azure_auth import AzureAuthService
from api.services.azure_auth import get_auth_service as _auth_singleton
from api.services.http_client import AzureHttpClient
from api.services.metrics import MetricsService
from api.services.metrics import get_metrics_service as _metrics_singleton
from api.services.storage import (
    DBContainerService,
    ExportsContainerService,
    get_db_storage as _db_storage_singleton,
    get_exports_storage as _exports_singleton,
)
from api.services.resource_export import (
    ResourceExportService,
    get_resource_export_service as _resource_singleton,
)
from api.services.cost_export import (
    CostExportService,
    get_cost_export_service as _cost_singleton,
)


# ── Auth + HTTP ───────────────────────────────────────────────────────────────

def get_auth_service_dep() -> AzureAuthService:
    """FastAPI dependency: process-wide AzureAuthService."""
    return _auth_singleton()


def get_http_client_dep(
    auth: AzureAuthService = Depends(get_auth_service_dep),
) -> AzureHttpClient:
    """FastAPI dependency: AzureHttpClient wired to current auth service."""
    return AzureHttpClient(auth)


# ── Metrics ───────────────────────────────────────────────────────────────────

def get_metrics_service_dep() -> MetricsService:
    """FastAPI dependency: process-wide MetricsService."""
    return _metrics_singleton()


# ── Storage ───────────────────────────────────────────────────────────────────

def get_db_storage_dep() -> DBContainerService:
    """FastAPI dependency: DBContainerService (optimizer-db blob)."""
    return _db_storage_singleton()


def get_exports_storage_dep() -> ExportsContainerService:
    """FastAPI dependency: ExportsContainerService (optimizer-exports blob)."""
    return _exports_singleton()


# ── Export services ───────────────────────────────────────────────────────────

def get_resource_export_dep() -> ResourceExportService:
    """FastAPI dependency: ResourceExportService."""
    return _resource_singleton()


def get_cost_export_dep() -> CostExportService:
    """FastAPI dependency: CostExportService."""
    return _cost_singleton()


# ── Annotated type aliases (optional ergonomic shorthand) ─────────────────────

DBSession         = Annotated[Session,                  Depends(get_db)]
AuthSvcDep        = Annotated[AzureAuthService,         Depends(get_auth_service_dep)]
HttpClientDep     = Annotated[AzureHttpClient,          Depends(get_http_client_dep)]
MetricsSvcDep     = Annotated[MetricsService,           Depends(get_metrics_service_dep)]
DBStorageDep      = Annotated[DBContainerService,       Depends(get_db_storage_dep)]
ExportsStorageDep = Annotated[ExportsContainerService,  Depends(get_exports_storage_dep)]
ResourceSvcDep    = Annotated[ResourceExportService,    Depends(get_resource_export_dep)]
CostSvcDep        = Annotated[CostExportService,        Depends(get_cost_export_dep)]