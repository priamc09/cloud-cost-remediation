"""Unit tests for api.config — Settings defaults and validation."""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch


def test_settings_defaults():
    """Provided env values are loaded correctly."""
    from api.config import Settings

    s = Settings()
    assert s.AZURE_TENANT_ID == "test-tenant-id"
    assert s.AZURE_CLIENT_ID == "test-client-id"
    assert s.AZURE_SUBSCRIPTION_ID == "test-subscription-id"
    assert s.DATABASE_PROVIDER == "sqlite"
    assert s.IDLE_VM_CPU_THRESHOLD_PCT == 5.0
    assert s.IDLE_AKS_CPU_THRESHOLD_PCT == 10.0
    assert s.ANALYSIS_LOOKBACK_DAYS == 30
    assert s.IDLE_STORAGE_DAYS == 30
    assert s.IDLE_APP_DAYS == 30
    assert s.IDLE_DB_DAYS == 30
    assert s.DB_POOL_SIZE == 5
    assert s.DB_MAX_OVERFLOW == 10


def test_settings_threshold_overrides():
    """Threshold values can be overridden via env."""
    from api.config import Settings

    with patch.dict(os.environ, {"IDLE_VM_CPU_THRESHOLD_PCT": "15.0",
                                  "ANALYSIS_LOOKBACK_DAYS": "14"}):
        s = Settings()
        assert s.IDLE_VM_CPU_THRESHOLD_PCT == 15.0
        assert s.ANALYSIS_LOOKBACK_DAYS == 14


def test_settings_missing_required_fields():
    """Missing required Azure fields should raise ValidationError."""
    from pydantic import ValidationError
    from api.config import get_settings
    get_settings.cache_clear()

    required_vars = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                     "AZURE_SUBSCRIPTION_ID", "AZURE_KEYVAULT_URL", "AZURE_STORAGE_ACCOUNT_URL"]
    # Remove all required vars and suppress .env file loading
    env_without_required = {k: v for k, v in os.environ.items() if k not in required_vars}
    with patch.dict(os.environ, env_without_required, clear=True):
        with pytest.raises((ValidationError, Exception)):
            from api.config import Settings
            Settings(_env_file=None)

    get_settings.cache_clear()  # restore cache state


def test_get_settings_is_cached():
    """get_settings() returns the same instance (lru_cache)."""
    from api.config import get_settings

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
