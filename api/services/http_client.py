"""
AzureHttpClient – thin httpx wrapper with automatic auth headers.

Logs every outbound request at DEBUG level and all errors at WARNING/ERROR.
Raises descriptive exceptions with HTTP status codes for callers to handle.
"""
from __future__ import annotations

import logging

import httpx

from api.services.azure_auth import AzureAuthService

logger = logging.getLogger(__name__)


class AzureHttpClientError(Exception):
    """Base exception for all AzureHttpClient failures."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AzureHttpTimeoutError(AzureHttpClientError):
    """Raised when an Azure ARM/Metrics/Cost Management request times out."""


class AzureHttpStatusError(AzureHttpClientError):
    """Raised when the Azure API returns a non-2xx response."""


class AzureHttpClient:
    """
    Thin httpx wrapper that injects Azure ARM auth headers on every request.
    All requests are logged at DEBUG; failures at WARNING (4xx) or ERROR (5xx/timeout).
    """

    DEFAULT_TIMEOUT = 60.0
    ARM_SCOPE = "https://management.azure.com/.default"

    def __init__(
        self,
        auth_service: AzureAuthService,
        scope: str = ARM_SCOPE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._auth = auth_service
        self._scope = scope
        self._timeout = timeout

    # ── core verbs ────────────────────────────────────────────────────────────

    def get(self, url: str, **kwargs) -> dict:
        """GET *url*, raise on HTTP error, return parsed JSON."""
        short_url = self._short(url)
        logger.debug("GET %s", short_url)
        try:
            resp = httpx.get(
                url,
                headers=self._auth.auth_headers(self._scope),
                timeout=self._timeout,
                **kwargs,
            )
            self._check(resp, "GET", short_url)
            logger.debug("GET %s → %d", short_url, resp.status_code)
            return resp.json()
        except (AzureHttpClientError, AzureHttpTimeoutError, AzureHttpStatusError):
            raise
        except httpx.TimeoutException as exc:
            logger.warning("GET %s timed out after %.0fs: %s", short_url, self._timeout, exc)
            raise AzureHttpTimeoutError(
                f"Request timed out: GET {short_url}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("GET %s network error: %s", short_url, exc, exc_info=True)
            raise AzureHttpClientError(f"Network error: GET {short_url}: {exc}") from exc

    def post(self, url: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """POST *url* with JSON body; return raw Response."""
        short_url = self._short(url)
        logger.debug("POST %s", short_url)
        try:
            resp = httpx.post(
                url,
                headers=self._auth.auth_headers(self._scope),
                json=json,
                timeout=self._timeout,
                **kwargs,
            )
            self._check(resp, "POST", short_url)
            logger.debug("POST %s → %d", short_url, resp.status_code)
            return resp
        except (AzureHttpClientError, AzureHttpTimeoutError, AzureHttpStatusError):
            raise
        except httpx.TimeoutException as exc:
            logger.warning("POST %s timed out after %.0fs: %s", short_url, self._timeout, exc)
            raise AzureHttpTimeoutError(
                f"Request timed out: POST {short_url}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("POST %s network error: %s", short_url, exc, exc_info=True)
            raise AzureHttpClientError(f"Network error: POST {short_url}: {exc}") from exc

    def get_raw_auth(self, url: str, **kwargs) -> httpx.Response:
        """GET *url* with Azure Bearer auth, returning raw Response (no JSON parse).

        Use this when you need auth but the response may not be JSON (e.g. 202
        empty body from long-running operation poll endpoints).
        """
        short_url = self._short(url)
        logger.debug("GET (authenticated-raw) %s", short_url)
        try:
            resp = httpx.get(
                url,
                headers=self._auth.auth_headers(self._scope),
                timeout=self._timeout,
                **kwargs,
            )
            logger.debug("GET (authenticated-raw) %s → %d | %d bytes",
                         short_url, resp.status_code, len(resp.content))
            return resp
        except httpx.TimeoutException as exc:
            logger.warning("GET (auth-raw) %s timed out: %s", short_url, exc)
            raise AzureHttpTimeoutError(f"Request timed out: GET {short_url}") from exc
        except httpx.RequestError as exc:
            logger.error("GET (auth-raw) %s network error: %s", short_url, exc, exc_info=True)
            raise AzureHttpClientError(f"Network error: GET {short_url}: {exc}") from exc

    def get_raw(self, url: str, **kwargs) -> httpx.Response:
        """GET *url* without auth (e.g. pre-signed blob SAS URLs)."""
        short_url = self._short(url)
        logger.debug("GET (unauthenticated) %s", short_url)
        try:
            resp = httpx.get(url, timeout=self._timeout, **kwargs)
            self._check(resp, "GET", short_url)
            logger.debug("GET (unauthenticated) %s → %d | %d bytes",
                         short_url, resp.status_code, len(resp.content))
            return resp
        except (AzureHttpClientError, AzureHttpTimeoutError, AzureHttpStatusError):
            raise
        except httpx.TimeoutException as exc:
            logger.warning("GET (raw) %s timed out: %s", short_url, exc)
            raise AzureHttpTimeoutError(f"Request timed out: GET {short_url}") from exc
        except httpx.RequestError as exc:
            logger.error("GET (raw) %s network error: %s", short_url, exc, exc_info=True)
            raise AzureHttpClientError(f"Network error: GET {short_url}: {exc}") from exc

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _check(resp: httpx.Response, method: str, short_url: str) -> None:
        """Raise AzureHttpStatusError for non-2xx responses with log context."""
        if resp.is_success:
            return
        body_preview = resp.text[:300] if resp.text else "<empty>"
        if 400 <= resp.status_code < 500:
            logger.warning(
                "%s %s → %d (client error): %s",
                method, short_url, resp.status_code, body_preview,
            )
        else:
            logger.error(
                "%s %s → %d (server error): %s",
                method, short_url, resp.status_code, body_preview,
            )
        raise AzureHttpStatusError(
            f"HTTP {resp.status_code} from {method} {short_url}: {body_preview}",
            status_code=resp.status_code,
        )

    @staticmethod
    def _short(url: str) -> str:
        """Truncate long URLs (strip SAS tokens) for log readability."""
        if "?" in url:
            url = url.split("?")[0] + "?…"
        return url[:120]