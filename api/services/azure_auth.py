"""
Azure authentication service.

Class hierarchy
───────────────
AzureAuthService
  – singleton; wraps ClientSecretCredential
  – get_token(scope)       → bearer token string
  – auth_headers(scope)    → {"Authorization": "Bearer ..."}
  – get_kv_secret(name)    → secret value from Key Vault
"""
from __future__ import annotations

import logging
from functools import lru_cache

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient

from api.config import get_settings

logger = logging.getLogger(__name__)


class AzureAuthService:
    """Wraps Azure SDK credential; instantiated once per process."""

    ARM_SCOPE = "https://management.azure.com/.default"

    def __init__(self) -> None:
        cfg = get_settings()
        logger.info(
            "Initialising AzureAuthService | tenant=%s client=%s",
            cfg.AZURE_TENANT_ID, cfg.AZURE_CLIENT_ID,
        )
        try:
            self._credential = ClientSecretCredential(
                tenant_id=cfg.AZURE_TENANT_ID,
                client_id=cfg.AZURE_CLIENT_ID,
                client_secret=cfg.AZURE_CLIENT_SECRET,
            )
        except Exception as exc:
            logger.critical(
                "Failed to initialise ClientSecretCredential: %s", exc, exc_info=True
            )
            raise
        self._kv_url: str = cfg.AZURE_KEYVAULT_URL

    # ── public API ────────────────────────────────────────────────────────────

    def get_token(self, scope: str = ARM_SCOPE) -> str:
        """Return a short-lived bearer token for *scope*."""
        logger.debug("Acquiring token | scope=%s", scope)
        try:
            token = self._credential.get_token(scope).token
            logger.debug("Token acquired successfully | scope=%s", scope)
            return token
        except ClientAuthenticationError as exc:
            logger.error(
                "Authentication failed for scope=%s: %s", scope, exc, exc_info=True
            )
            raise
        except Exception as exc:
            logger.error("Unexpected error acquiring token: %s", exc, exc_info=True)
            raise

    def auth_headers(self, scope: str = ARM_SCOPE) -> dict[str, str]:
        """Return an Authorization header dict ready to pass to httpx."""
        return {"Authorization": f"Bearer {self.get_token(scope)}"}

    def get_kv_secret(self, secret_name: str) -> str:
        """Fetch a secret value from Azure Key Vault."""
        logger.debug("Fetching Key Vault secret | name=%s vault=%s", secret_name, self._kv_url)
        try:
            client = SecretClient(vault_url=self._kv_url, credential=self._credential)
            value = client.get_secret(secret_name).value
            logger.debug("Key Vault secret fetched | name=%s", secret_name)
            return value
        except HttpResponseError as exc:
            logger.error(
                "Key Vault HTTP error fetching secret '%s': status=%s message=%s",
                secret_name, exc.status_code, exc.message, exc_info=True,
            )
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error fetching KV secret '%s': %s", secret_name, exc, exc_info=True
            )
            raise


# ── Process-wide singleton ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_auth_service() -> AzureAuthService:
    """Return the process-wide AzureAuthService instance."""
    return AzureAuthService()


# ── Module-level shims (backward compatibility) ───────────────────────────────

def get_token(scope: str = AzureAuthService.ARM_SCOPE) -> str:
    return get_auth_service().get_token(scope)


def auth_headers(scope: str = AzureAuthService.ARM_SCOPE) -> dict[str, str]:
    return get_auth_service().auth_headers(scope)


def get_kv_secret(secret_name: str) -> str:
    return get_auth_service().get_kv_secret(secret_name)