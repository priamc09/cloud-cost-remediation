"""
DatabaseProviderFactory – selects and returns the configured provider.

Set DATABASE_PROVIDER in .env (or environment):
    sqlite      → SQLiteProvider       (default, no extra driver)
    postgresql  → PostgreSQLProvider   (psycopg2-binary)
    mysql       → MySQLProvider        (pymysql)
    sqlserver   → SQLServerProvider    (pyodbc + ODBC Driver 18)
"""
from __future__ import annotations

import logging
from functools import lru_cache

from api.db.base import BaseDatabaseProvider

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BaseDatabaseProvider]] = {}


def _register():
    """Lazy import to avoid loading DB drivers at module init time."""
    global _REGISTRY
    from api.db.sqlite_provider import SQLiteProvider
    from api.db.postgresql_provider import PostgreSQLProvider
    from api.db.mysql_provider import MySQLProvider
    from api.db.sqlserver_provider import SQLServerProvider
    _REGISTRY = {
        "sqlite":     SQLiteProvider,
        "postgresql": PostgreSQLProvider,
        "mysql":      MySQLProvider,
        "sqlserver":  SQLServerProvider,
    }


@lru_cache(maxsize=1)
def get_db_provider() -> BaseDatabaseProvider:
    """Return the configured BaseDatabaseProvider singleton."""
    from api.config import get_settings
    _register()
    cfg = get_settings()
    name = getattr(cfg, "DATABASE_PROVIDER", "sqlite").lower()
    provider_cls = _REGISTRY.get(name)
    if provider_cls is None:
        raise ValueError(
            f"Unknown DATABASE_PROVIDER='{name}'. "
            f"Valid values: {', '.join(_REGISTRY)}"
        )
    provider = provider_cls()
    provider.validate()
    logger.info("[db] Using database provider: %s", provider)
    return provider