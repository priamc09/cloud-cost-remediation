"""
Database engine + session factory.

The active provider is chosen by DATABASE_PROVIDER in .env:
    sqlite      (default) – local file synced to Azure Blob Storage
    postgresql            – psycopg2
    mysql                 – pymysql
    sqlserver             – pyodbc

All models share the single Base from api.db.base.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session

from api.db.base import Base  # re-exported so models import from here
from api.db.factory import get_db_provider

logger = logging.getLogger(__name__)


# ── Engine (built once per process) ──────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    provider = get_db_provider()
    logger.info("Creating SQLAlchemy engine via %s", provider)
    try:
        engine = provider.create_engine()
        # Smoke-test: verify connectivity at startup
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database engine connected successfully.")
        return engine
    except OperationalError as exc:
        logger.critical(
            "Cannot connect to database (%s): %s",
            provider, exc,
            exc_info=True,
        )
        raise
    except Exception as exc:
        logger.critical("Unexpected error creating database engine: %s", exc, exc_info=True)
        raise


# ── Session factory ───────────────────────────────────────────────────────────

_SessionLocal: sessionmaker | None = None


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def SessionLocal() -> Session:  # type: ignore[return-value]
    """Return a new SQLAlchemy Session from the process-wide factory."""
    return _get_session_factory()()


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db():
    """Yield a DB session; always closed on exit. Use as FastAPI Depends(get_db)."""
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        logger.error("SQLAlchemy error during request session: %s", exc, exc_info=True)
        db.rollback()
        raise
    except Exception as exc:
        logger.error("Unexpected error during request session: %s", exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


# ── Table creation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they do not exist (safe to call repeatedly)."""
    try:
        import api.models  # noqa: F401 – registers models on Base.metadata
        Base.metadata.create_all(bind=_get_engine())
        table_names = list(Base.metadata.tables.keys())
        logger.info("Tables ensured: %s", table_names)
    except SQLAlchemyError as exc:
        logger.critical("init_db failed: %s", exc, exc_info=True)
        raise