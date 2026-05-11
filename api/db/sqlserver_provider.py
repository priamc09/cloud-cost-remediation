"""
SQLServerProvider – uses pyodbc via mssql+pyodbc driver string.

Required packages: pyodbc  (+ ODBC Driver 18 for SQL Server installed)
Config env vars:
    DB_HOST, DB_PORT (1433), DB_NAME, DB_USER, DB_PASSWORD
    DB_DRIVER (ODBC Driver 18 for SQL Server)
    DB_ENCRYPT (yes | no)
    DB_TRUST_SERVER_CERT (no | yes)
"""
from __future__ import annotations
import urllib.parse
from api.db.base import BaseDatabaseProvider
from api.config import get_settings


class SQLServerProvider(BaseDatabaseProvider):
    """Microsoft SQL Server / Azure SQL via pyodbc."""

    @property
    def connection_url(self) -> str:
        cfg = get_settings()
        driver  = getattr(cfg, "DB_DRIVER", "ODBC Driver 18 for SQL Server")
        encrypt = getattr(cfg, "DB_ENCRYPT", "yes")
        trust   = getattr(cfg, "DB_TRUST_SERVER_CERT", "no")
        odbc = (
            f"DRIVER={{{driver}}};"
            f"SERVER={cfg.DB_HOST},{cfg.DB_PORT};"
            f"DATABASE={cfg.DB_NAME};"
            f"UID={cfg.DB_USER};"
            f"PWD={cfg.DB_PASSWORD};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust};"
        )
        return f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(odbc)}"

    @property
    def engine_kwargs(self) -> dict:
        cfg = get_settings()
        return {
            "pool_size": getattr(cfg, "DB_POOL_SIZE", 5),
            "max_overflow": getattr(cfg, "DB_MAX_OVERFLOW", 10),
            "pool_pre_ping": True,
            "fast_executemany": True,
        }

    def validate(self) -> None:
        try:
            import pyodbc  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SQL Server requires 'pyodbc'. Run: uv pip install pyodbc"
            ) from exc