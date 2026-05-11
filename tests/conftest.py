"""
Shared pytest fixtures for the Cloud Cost Optimizer test suite.

Provides:
  - env_settings   : patches Settings with in-memory/fake Azure values
  - db_session     : in-memory SQLite session (no blob, no KV)
  - client         : FastAPI TestClient with DB + storage overrides
  - sample_resource: a minimal ARM resource dict
  - sample_finding : a minimal Finding pydantic object
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Environment must be patched before any api.* imports ──────────────────────

FAKE_ENV = {
    "AZURE_TENANT_ID": "test-tenant-id",
    "AZURE_CLIENT_ID": "test-client-id",
    "AZURE_CLIENT_SECRET": "test-client-secret",
    "AZURE_SUBSCRIPTION_ID": "test-subscription-id",
    "AZURE_KEYVAULT_URL": "https://fake-vault.vault.azure.net/",
    "AZURE_STORAGE_ACCOUNT_URL": "https://fakestorage.blob.core.windows.net",
    "DATABASE_PROVIDER": "sqlite",
    "LOCAL_DB_PATH": "/tmp/test_optimizer.db",
    "DB_BLOB_NAME": "optimizer.db",
    "AZURE_DB_CONTAINER_NAME": "optimizer-db",
    "AZURE_EXPORTS_CONTAINER_NAME": "optimizer-exports",
    "KV_SECRET_DB_SAS": "storage-db-sas-token",
    "KV_SECRET_EXPORTS_SAS": "storage-exports-sas-token",
}


@pytest.fixture(scope="session", autouse=True)
def patch_env():
    """Patch os.environ before any api imports happen."""
    with patch.dict(os.environ, FAKE_ENV, clear=False):
        yield


# ── In-memory DB ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Return a fresh in-memory SQLite session for each test."""
    # Import here so env patch is already active
    import api.models  # noqa: F401 – registers ORM models on Base.metadata
    from api.db.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture()
def client(db_session):
    """
    FastAPI TestClient with:
      - DB dependency overridden to in-memory SQLite
      - Blob storage + auth dependencies mocked out
      - Lifespan (blob download/upload) bypassed
    """
    from api.main import app
    from api.database import get_db
    from api.dependencies import get_db_storage_dep, get_exports_storage_dep
    from api.services.storage import DBContainerService, ExportsContainerService

    def override_get_db():
        yield db_session

    mock_db_storage = MagicMock(spec=DBContainerService)
    mock_exports_storage = MagicMock(spec=ExportsContainerService)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_storage_dep] = lambda: mock_db_storage
    app.dependency_overrides[get_exports_storage_dep] = lambda: mock_exports_storage

    with patch("api.main.get_db_storage_dep", return_value=mock_db_storage), \
         patch("api.main.init_db"), \
         patch("api.services.storage.get_kv_secret", return_value="fake-sas?sv=2023"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ── Shared data fixtures ──────────────────────────────────────────────────────

@pytest.fixture()
def sample_resource() -> dict:
    return {
        "resource_id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        "name": "vm1",
        "type": "microsoft.compute/virtualmachines",
        "resource_group": "rg1",
        "subscription_id": "test-sub",
        "location": "eastus",
        "tags": {"env": "test"},
        "sku": None,
        "kind": None,
    }


@pytest.fixture()
def sample_disk_resource() -> dict:
    return {
        "resource_id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/disks/disk1",
        "name": "disk1",
        "type": "microsoft.compute/disks",
        "resource_group": "rg1",
        "subscription_id": "test-sub",
        "location": "eastus",
        "tags": {},
        "sku": None,
        "kind": None,
    }


@pytest.fixture()
def mock_metrics():
    """Return a MagicMock standing in for MetricsService."""
    m = MagicMock()
    m.get_metric_average.return_value = None
    m.get_metric_total.return_value = None
    m.get_arm_resource.return_value = None
    return m


@pytest.fixture()
def run_id() -> str:
    return str(uuid.uuid4())
