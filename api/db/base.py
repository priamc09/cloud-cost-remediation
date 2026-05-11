"""
BaseDatabaseProvider – abstract contract for all database back-ends.

Hierarchy
─────────
BaseDatabaseProvider (ABC)
  ├─ SQLiteProvider
  ├─ PostgreSQLProvider
  ├─ MySQLProvider
  └─ SQLServerProvider

Each provider is responsible for:
  • building the SQLAlchemy connection URL
  • supplying engine kwargs (pool size, connect_args, …)
  • optional pre-flight validation (e.g. checking the driver is installed)

Usage
─────
    from api.db.factory import get_db_provider
    provider = get_db_provider()
    engine   = provider.create_engine()
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Single DeclarativeBase shared by all models, regardless of backend."""
    pass


class BaseDatabaseProvider(ABC):
    """Abstract database provider. Concrete subclasses implement URL + kwargs."""

    # ── abstract interface ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def connection_url(self) -> str:
        """Return the SQLAlchemy connection URL string."""

    @property
    def engine_kwargs(self) -> dict:
        """Return extra keyword arguments passed to create_engine()."""
        return {}

    # ── concrete helpers ──────────────────────────────────────────────────────

    def create_engine(self, echo: bool = False) -> Engine:
        """Build and return a SQLAlchemy Engine."""
        return create_engine(self.connection_url, echo=echo, **self.engine_kwargs)

    def validate(self) -> None:
        """
        Optional: raise ImportError / ValueError if required driver or
        config is missing. Called by factory before returning the provider.
        """

    def __repr__(self) -> str:
        # Mask password in logs
        import re
        safe = re.sub(r"://[^:]+:[^@]+@", "://<redacted>@", self.connection_url)
        return f"{self.__class__.__name__}({safe})"