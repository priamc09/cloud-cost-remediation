"""
MySQLProvider – uses PyMySQL driver (pure-Python, no native libs needed).

Required packages: pymysql
Config env vars:
    DB_HOST, DB_PORT (3306), DB_NAME, DB_USER, DB_PASSWORD
    DB_CHARSET (utf8mb4)
"""
from __future__ import annotations
from api.db.base import BaseDatabaseProvider
from api.config import get_settings


class MySQLProvider(BaseDatabaseProvider):
    """MySQL / MariaDB via PyMySQL driver."""

    @property
    def connection_url(self) -> str:
        cfg = get_settings()
        charset = getattr(cfg, "DB_CHARSET", "utf8mb4")
        return (
            f"mysql+pymysql://{cfg.DB_USER}:{cfg.DB_PASSWORD}"
            f"@{cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}"
            f"?charset={charset}"
        )

    @property
    def engine_kwargs(self) -> dict:
        cfg = get_settings()
        return {
            "pool_size": getattr(cfg, "DB_POOL_SIZE", 5),
            "max_overflow": getattr(cfg, "DB_MAX_OVERFLOW", 10),
            "pool_pre_ping": True,
            "pool_recycle": 3600,   # avoid stale connections
        }

    def validate(self) -> None:
        try:
            import pymysql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "MySQL requires 'pymysql'. Run: uv pip install pymysql"
            ) from exc