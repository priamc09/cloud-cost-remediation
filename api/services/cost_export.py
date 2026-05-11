"""
CostExportService – queries Azure Cost Management (synchronous Query API).

Uses the synchronous POST /query endpoint which returns data immediately.
Only falls back to a short 10-second poll if the API responds with 202.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from functools import lru_cache  # noqa: F401 used by factory below

from api.config import get_settings
from api.services.azure_auth import get_auth_service
from api.services.http_client import AzureHttpClient, AzureHttpClientError, AzureHttpStatusError

logger = logging.getLogger(__name__)

COST_MGMT_BASE = "https://management.azure.com"
# Cost Management API allows max 1 month (31 days) per request
_MAX_COST_DAYS = 31
# Short poll budget for the rare 202 response (seconds)
_POLL_MAX_WAIT = 10
_POLL_INTERVAL = 5


class CostExportService:
    """Fetches cost data via the synchronous Cost Management Query API."""

    def __init__(self, http_client: AzureHttpClient) -> None:
        self._http = http_client

    def fetch_cost_by_resource(self) -> list[dict]:
        """Query Cost Management and return per-resource cost records."""
        cfg = get_settings()
        sub_id = cfg.AZURE_SUBSCRIPTION_ID
        lookback = min(cfg.ANALYSIS_LOOKBACK_DAYS, _MAX_COST_DAYS)
        _now = datetime.utcnow()
        _end = _now.strftime("%Y-%m-%d")
        _start = (_now - timedelta(days=lookback)).strftime("%Y-%m-%d")

        query_url = (
            f"{COST_MGMT_BASE}/subscriptions/{sub_id}"
            "/providers/Microsoft.CostManagement/query"
            "?api-version=2023-11-01"
        )
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": _start, "to": _end},
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceType"},
                    {"type": "Dimension", "name": "ResourceGroupName"},
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "MeterSubcategory"},
                    {"type": "Dimension", "name": "ResourceLocation"},
                ],
            },
        }

        logger.info(
            "Querying Cost Management | subscription=%s period=%s to %s",
            sub_id, _start, _end,
        )
        try:
            resp = self._http.post(query_url, json=body)
        except AzureHttpStatusError as exc:
            logger.error(
                "Cost query failed | HTTP %s: %s", exc.status_code, exc, exc_info=True
            )
            raise
        except AzureHttpClientError as exc:
            logger.error("Cost query network error: %s", exc, exc_info=True)
            raise

        # Normally 200 with JSON body — rare 202 means deferred result
        if resp.status_code == 202:
            location = resp.headers.get("Location") or resp.headers.get("Azure-AsyncOperation")
            if location:
                logger.info("Cost query deferred (202) | polling up to %ds…", _POLL_MAX_WAIT)
                data = self._poll_query(location)
            else:
                logger.error("Cost query 202 but no Location header: %s", dict(resp.headers))
                return []
        else:
            try:
                data = resp.json()
            except Exception as exc:
                logger.error("Cost query returned non-JSON body: %s | body=%s",
                             exc, resp.text[:500])
                return []

        records = self._parse_query_response(data, sub_id)
        logger.info(
            "Cost export complete | records=%d period=%s to %s",
            len(records), _start, _end,
        )
        # Log top spenders for visibility
        for r in sorted(records, key=lambda x: x["cost_usd"], reverse=True)[:5]:
            logger.info(
                "  Top cost | resource=%s type=%s cost=%.4f %s",
                r["resource_id"][-60:] or "(untagged)",
                r["resource_type"],
                r["cost_usd"],
                r["currency"],
            )
        return records

    def _poll_query(self, location: str) -> dict:
        """Poll a deferred query result for up to _POLL_MAX_WAIT seconds."""
        waited = 0
        while waited < _POLL_MAX_WAIT:
            time.sleep(_POLL_INTERVAL)
            waited += _POLL_INTERVAL
            logger.debug("Polling deferred cost query | waited=%ds", waited)
            try:
                resp = self._http.get_raw_auth(location)
            except AzureHttpClientError as exc:
                logger.warning("Cost poll error (waited %ds): %s", waited, exc)
                continue
            if resp.status_code == 202:
                logger.debug("Still deferred (202) | waited=%ds", waited)
                continue
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as exc:
                    logger.error("Cost poll non-JSON 200: %s | body=%s", exc, resp.text[:300])
                    return {}
            logger.warning("Cost poll unexpected status %d | body=%s",
                           resp.status_code, resp.text[:300])
        logger.warning("Cost query poll timed out after %ds — returning empty.", _POLL_MAX_WAIT)
        return {}

    @staticmethod
    def _parse_query_response(data: dict, sub_id: str) -> list[dict]:
        """Parse the tabular Query API response into flat dicts."""
        props = data.get("properties", data)  # some responses wrap in properties
        columns = [c["name"] for c in props.get("columns", [])]
        rows = props.get("rows", [])

        if not columns:
            logger.warning("Cost query response has no columns — raw keys: %s", list(data.keys()))
            logger.debug("Full cost response: %s", str(data)[:1000])
            return []

        logger.debug("Cost query columns: %s | row_count=%d", columns, len(rows))

        def col(row: list, name: str, default="") -> str:
            try:
                return str(row[columns.index(name)]) if name in columns else default
            except (IndexError, ValueError):
                return default

        records = []
        for row in rows:
            cost_val = col(row, "Cost", "0")
            records.append({
                "resource_id": col(row, "ResourceId").lower(),
                "resource_name": col(row, "ResourceId").split("/")[-1],
                "resource_type": col(row, "ResourceType"),
                "resource_group": col(row, "ResourceGroupName"),
                "resource_location": col(row, "ResourceLocation"),
                "subscription_id": sub_id,
                "service_name": col(row, "ServiceName"),
                "service_tier": col(row, "MeterSubcategory"),
                "cost_usd": CostExportService._safe_float(cost_val),
                "currency": col(row, "Currency", "USD"),
            })
        return records

    @staticmethod
    def _safe_float(val: str) -> float:
        try:
            return float(str(val).replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0


@lru_cache(maxsize=1)
def get_cost_export_service() -> CostExportService:
    return CostExportService(AzureHttpClient(get_auth_service()))


def fetch_cost_by_resource() -> list[dict]:
    return get_cost_export_service().fetch_cost_by_resource()