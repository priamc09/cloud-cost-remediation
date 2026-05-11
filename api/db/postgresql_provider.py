"""
PostgreSQLProvider – uses asyncpg driver via psycopg2 sync interface.

Required packages: psycopg2-binary  (or psycopg2)
Config env vars:
    DB_HOST, DB_PORT (5432), DB_NAME, DB_USER, DB_PASSWORD
    DB_SSL_MODE (disable | require | verify-full)
"""
from __future__ import annotations
from api.db.base import BaseDatabaseProvider
from api.config import get_settings


class PostgreSQLProvider(BaseDatabaseProvider):
    """PostgreSQL via psycopg2 driver."""

    @property
    def connection_url(self) -> str:
        cfg = get_settings()
        ssl = getattr(cfg, "DB_SSL_MODE", "require")
        return (
            f"postgresql+psycopg2://{cfg.DB_USER}:{cfg.DB_PASSWORD}"
            f"@{cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}"
            f"?sslmode={ssl}"
        )

    @property
    def engine_kwargs(self) -> dict:
        cfg = get_settings()
        return {
            "pool_size": getattr(cfg, "DB_POOL_SIZE", 5),
            "max_overflow": getattr(cfg, "DB_MAX_OVERFLOW", 10),
            "pool_pre_ping": True,
        }

    def validate(self) -> None:
        try:
            import psycopg2  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PostgreSQL requires 'psycopg2-binary'. "
                "Run: uv pip install psycopg2-binary"
            ) from exc