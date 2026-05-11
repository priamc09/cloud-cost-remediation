"""
ResourceExportService – fetches all resources via Azure Resource Graph + ARM fallback.

Azure Resource Graph (ARG) is preferred: it covers all resource types, handles
pagination efficiently with skipToken, and is faster than ARM list.
ARG endpoint: POST https://management.azure.com/providers/Microsoft.ResourceGraph/resources
"""
from __future__ import annotations

import logging
from functools import lru_cache  # noqa: F401 used by factory below

from api.config import get_settings
from api.services.azure_auth import get_auth_service
from api.services.http_client import AzureHttpClient, AzureHttpClientError, AzureHttpStatusError

logger = logging.getLogger(__name__)

ARM_BASE = "https://management.azure.com"
ARM_API_VERSION = "2021-04-01"
ARG_API_VERSION = "2022-10-01"
_PAGE_SIZE = 1000


class ResourceExportService:
    """Retrieves all ARM resources via Azure Resource Graph (with ARM list fallback)."""

    def __init__(self, http_client: AzureHttpClient) -> None:
        self._http = http_client

    def fetch_all(self) -> list[dict]:
        """Return all subscription resources. Tries ARG first, falls back to ARM list."""
        sub_id = get_settings().AZURE_SUBSCRIPTION_ID
        logger.info("Starting resource export | subscription=%s", sub_id)
        try:
            resources = self._fetch_via_resource_graph(sub_id)
            logger.info(
                "Resource Graph export complete | total_resources=%d", len(resources)
            )
            if not resources:
                logger.warning(
                    "Resource Graph returned 0 resources — subscription may be empty "
                    "or SP lacks Reader role. Trying ARM list as fallback…"
                )
                resources = self._fetch_via_arm_list(sub_id)
            return resources
        except Exception as exc:
            logger.warning(
                "Resource Graph failed (%s) — falling back to ARM list", exc
            )
            return self._fetch_via_arm_list(sub_id)

    def _fetch_via_resource_graph(self, sub_id: str) -> list[dict]:
        """Query all resources via Azure Resource Graph (ARG)."""
        arg_url = (
            f"{ARM_BASE}/providers/Microsoft.ResourceGraph/resources"
            f"?api-version={ARG_API_VERSION}"
        )
        query = (
            "Resources "
            "| project id, name, type, resourceGroup, subscriptionId, location, tags, sku, kind "
            "| order by type asc"
        )
        body: dict = {
            "subscriptions": [sub_id],
            "query": query,
            "options": {"$top": _PAGE_SIZE},
        }
        resources: list[dict] = []
        page = 0
        while True:
            page += 1
            logger.debug("ARG page %d | fetching up to %d resources", page, _PAGE_SIZE)
            resp = self._http.post(arg_url, json=body)
            data = resp.json()
            batch = data.get("data", [])
            logger.debug("ARG page %d | got %d resources", page, len(batch))
            for item in batch:
                resources.append(self._normalise_arg(item))
            skip_token = data.get("$skipToken")
            if not skip_token or not batch:
                break
            body["options"] = {"$top": _PAGE_SIZE, "$skipToken": skip_token}
        logger.info("ARG query complete | pages=%d total=%d", page, len(resources))
        return resources

    def _fetch_via_arm_list(self, sub_id: str) -> list[dict]:
        """Fallback: ARM /subscriptions/{sub}/resources list endpoint."""
        url: str | None = (
            f"{ARM_BASE}/subscriptions/{sub_id}"
            f"/resources?api-version={ARM_API_VERSION}&$top={_PAGE_SIZE}"
        )
        resources: list[dict] = []
        page = 0
        while url:
            page += 1
            logger.debug("ARM list page %d", page)
            data = self._http.get(url)
            batch = data.get("value", [])
            logger.debug("ARM page %d: %d resources", page, len(batch))
            for item in batch:
                resources.append(self._normalise(item))
            url = data.get("nextLink")
        logger.info("ARM list complete | pages=%d total=%d", page, len(resources))
        return resources

    @staticmethod
    def _normalise_arg(item: dict) -> dict:
        """Normalise an Azure Resource Graph row."""
        rid = item.get("id", "")
        rg = item.get("resourceGroup", "")
        sku = item.get("sku")
        return {
            "resource_id": rid,
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "resource_group": rg,
            "subscription_id": item.get("subscriptionId", get_settings().AZURE_SUBSCRIPTION_ID),
            "location": item.get("location", ""),
            "tags": item.get("tags") or {},
            "sku": sku.get("name") if isinstance(sku, dict) else (
                str(sku) if sku else None
            ),
            "kind": item.get("kind"),
        }

    @staticmethod
    def _normalise(item: dict) -> dict:
        """Normalise an ARM list resource row."""
        rid = item.get("id", "")
        parts = rid.lower().split("/")
        rg = ""
        try:
            idx = parts.index("resourcegroups")
            rg = rid.split("/")[idx + 1]
        except (ValueError, IndexError):
            logger.debug("Could not extract resource group from id: %s", rid[:80])
        sku = item.get("sku")
        return {
            "resource_id": rid,
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "resource_group": rg,
            "subscription_id": get_settings().AZURE_SUBSCRIPTION_ID,
            "location": item.get("location", ""),
            "tags": item.get("tags") or {},
            "sku": sku.get("name") if isinstance(sku, dict) else None,
            "kind": item.get("kind"),
        }


@lru_cache(maxsize=1)
def get_resource_export_service() -> ResourceExportService:
    return ResourceExportService(AzureHttpClient(get_auth_service()))


def fetch_all_resources() -> list[dict]:
    return get_resource_export_service().fetch_all()