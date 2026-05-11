"""
SQLiteProvider – local file-based SQLite (default / free-tier).

No extra driver required; ships with Python.
The DB file is kept in LOCAL_DB_PATH and synced to Azure Blob Storage
by DBContainerService on startup/shutdown.
"""
from __future__ import annotations
from api.db.base import BaseDatabaseProvider
from api.config import get_settings


class SQLiteProvider(BaseDatabaseProvider):
    """SQLite backed by a local file (synced to blob storage)."""

    @property
    def connection_url(self) -> str:
        return f"sqlite:///{get_settings().LOCAL_DB_PATH}"

    @property
    def engine_kwargs(self) -> dict:
        return {"connect_args": {"check_same_thread": False}}