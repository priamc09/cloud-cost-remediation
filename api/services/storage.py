"""
Azure Blob Storage services.

Class hierarchy
───────────────
BlobContainerService               – base; resolves SAS token + builds ContainerClient
  ├─ DBContainerService            – optimizer-db container (download/upload DB file)
  └─ ExportsContainerService       – optimizer-exports container (upload/download files)
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.storage.blob import BlobClient, ContainerClient

from api.config import get_settings
from api.services.azure_auth import get_kv_secret

logger = logging.getLogger(__name__)


# ── Base service ──────────────────────────────────────────────────────────────

class BlobContainerService:
    """
    Base blob-container service.
    Subclasses supply container_name and kv_secret_name.
    """

    def __init__(self, container_name: str, kv_secret_name: str) -> None:
        self._container_name = container_name
        self._kv_secret_name = kv_secret_name
        cfg = get_settings()
        self._storage_account_url = cfg.AZURE_STORAGE_ACCOUNT_URL.rstrip("/")
        logger.debug(
            "BlobContainerService init | container=%s kv_secret=%s",
            container_name, kv_secret_name,
        )

    # ── internal ──────────────────────────────────────────────────────────────

    def _client(self) -> ContainerClient:
        """Build a fresh ContainerClient with a current SAS token from Key Vault."""
        try:
            sas = get_kv_secret(self._kv_secret_name)
        except Exception as exc:
            logger.error(
                "Cannot retrieve SAS token for container '%s' (secret=%s): %s",
                self._container_name, self._kv_secret_name, exc, exc_info=True,
            )
            raise
        url = f"{self._storage_account_url}/{self._container_name}?{sas}"
        return ContainerClient.from_container_url(url)

    def _blob_client(self, blob_name: str) -> BlobClient:
        return self._client().get_blob_client(blob_name)

    # ── shared helpers ────────────────────────────────────────────────────────

    def upload_bytes(self, blob_name: str, data: bytes, overwrite: bool = True) -> None:
        logger.debug("upload_bytes | container=%s blob=%s size=%d",
                     self._container_name, blob_name, len(data))
        try:
            self._blob_client(blob_name).upload_blob(data, overwrite=overwrite)
            logger.info("Blob uploaded | container=%s blob=%s bytes=%d",
                        self._container_name, blob_name, len(data))
        except HttpResponseError as exc:
            logger.error(
                "Blob upload failed | container=%s blob=%s status=%s: %s",
                self._container_name, blob_name, exc.status_code, exc.message, exc_info=True,
            )
            raise

    def download_bytes(self, blob_name: str) -> bytes:
        logger.debug("download_bytes | container=%s blob=%s", self._container_name, blob_name)
        try:
            data = self._blob_client(blob_name).download_blob().readall()
            logger.debug("Blob downloaded | container=%s blob=%s bytes=%d",
                         self._container_name, blob_name, len(data))
            return data
        except ResourceNotFoundError:
            # Callers (e.g. download_db on first run) handle this gracefully
            raise
        except HttpResponseError as exc:
            logger.error(
                "Blob download failed | container=%s blob=%s status=%s: %s",
                self._container_name, blob_name, exc.status_code, exc.message, exc_info=True,
            )
            raise

    def upload_file(self, blob_name: str, local_path: str | Path, overwrite: bool = True) -> str:
        """Upload a local file; returns blob_name."""
        local_path = Path(local_path)
        size = local_path.stat().st_size if local_path.exists() else 0
        logger.debug("upload_file | container=%s blob=%s file=%s size=%d",
                     self._container_name, blob_name, local_path, size)
        try:
            with open(local_path, "rb") as fh:
                self._blob_client(blob_name).upload_blob(fh, overwrite=overwrite)
            logger.info("File uploaded | container=%s blob=%s file=%s",
                        self._container_name, blob_name, local_path)
            return blob_name
        except FileNotFoundError:
            logger.error("upload_file: local file not found: %s", local_path)
            raise
        except HttpResponseError as exc:
            logger.error(
                "File upload failed | container=%s blob=%s status=%s: %s",
                self._container_name, blob_name, exc.status_code, exc.message, exc_info=True,
            )
            raise


# ── DB container ──────────────────────────────────────────────────────────────

class DBContainerService(BlobContainerService):
    """Manages the optimizer-db container (single SQLite blob)."""

    def __init__(self) -> None:
        cfg = get_settings()
        super().__init__(
            container_name=cfg.AZURE_DB_CONTAINER_NAME,
            kv_secret_name=cfg.KV_SECRET_DB_SAS,
        )
        self._local_path = Path(cfg.LOCAL_DB_PATH)
        self._blob_name: str = cfg.DB_BLOB_NAME

    def download_db(self) -> None:
        """Download optimizer.db from blob → LOCAL_DB_PATH. Safe on first run (blob may not exist)."""
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading DB blob | blob=%s → local=%s", self._blob_name, self._local_path)
        try:
            data = self.download_bytes(self._blob_name)
            self._local_path.write_bytes(data)
            logger.info("DB blob download complete | local=%s bytes=%d",
                        self._local_path, len(data))
        except ResourceNotFoundError:
            logger.warning(
                "DB blob '%s' not found in container '%s' — starting with a fresh database. "
                "This is expected on first run.",
                self._blob_name, self._container_name,
            )
        except Exception as exc:
            logger.error(
                "DB blob download failed | blob=%s: %s", self._blob_name, exc, exc_info=True
            )
            raise

    def upload_db(self) -> None:
        """Upload LOCAL_DB_PATH → optimizer.db blob."""
        if not self._local_path.exists():
            logger.warning(
                "upload_db: local DB file not found at %s — skipping upload.",
                self._local_path,
            )
            return
        size = self._local_path.stat().st_size
        logger.info("Uploading DB blob | local=%s bytes=%d → blob=%s",
                    self._local_path, size, self._blob_name)
        try:
            self.upload_file(self._blob_name, self._local_path)
            logger.info("DB blob upload complete | blob=%s", self._blob_name)
        except Exception as exc:
            logger.error(
                "DB blob upload failed | local=%s blob=%s: %s",
                self._local_path, self._blob_name, exc, exc_info=True,
            )
            raise


# ── Exports container ─────────────────────────────────────────────────────────

class ExportsContainerService(BlobContainerService):
    """Manages the optimizer-exports container (CSVs, PS1 scripts)."""

    def __init__(self) -> None:
        cfg = get_settings()
        super().__init__(
            container_name=cfg.AZURE_EXPORTS_CONTAINER_NAME,
            kv_secret_name=cfg.KV_SECRET_EXPORTS_SAS,
        )

    def upload_export(self, blob_name: str, local_path: str | Path) -> str:
        """Upload a local file to exports; returns blob_name."""
        logger.info("Uploading export | blob=%s file=%s", blob_name, local_path)
        try:
            result = self.upload_file(blob_name, local_path)
            logger.info("Export upload complete | blob=%s", blob_name)
            return result
        except Exception as exc:
            logger.error(
                "Export upload failed | blob=%s file=%s: %s",
                blob_name, local_path, exc, exc_info=True,
            )
            raise

    def get_export_blob_bytes(self, blob_name: str) -> bytes:
        """Download a blob from exports as bytes."""
        logger.debug("Downloading export blob | blob=%s", blob_name)
        try:
            data = self.download_bytes(blob_name)
            logger.debug("Export blob downloaded | blob=%s bytes=%d", blob_name, len(data))
            return data
        except ResourceNotFoundError:
            logger.warning("Export blob not found | blob=%s", blob_name)
            raise
        except Exception as exc:
            logger.error(
                "Export blob download failed | blob=%s: %s", blob_name, exc, exc_info=True
            )
            raise


# ── Process-wide singletons ───────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_db_storage() -> DBContainerService:
    return DBContainerService()


@lru_cache(maxsize=1)
def get_exports_storage() -> ExportsContainerService:
    return ExportsContainerService()


# ── Module-level shims (backward compatibility) ───────────────────────────────

def download_db() -> None:
    get_db_storage().download_db()


def upload_db() -> None:
    get_db_storage().upload_db()


def upload_export(blob_name: str, local_path: str) -> str:
    return get_exports_storage().upload_export(blob_name, local_path)


def get_export_blob_bytes(blob_name: str) -> bytes:
    return get_exports_storage().get_export_blob_bytes(blob_name)