"""
MetricsService – Azure Monitor Metrics + ARM property helpers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from api.config import get_settings
from api.services.azure_auth import get_auth_service
from api.services.http_client import AzureHttpClient, AzureHttpStatusError, AzureHttpTimeoutError

logger = logging.getLogger(__name__)
ARM_BASE = "https://management.azure.com"


class MetricsService:
    """Queries Azure Monitor Metrics, ARM properties, and Activity Logs."""

    def __init__(self, http_client: AzureHttpClient) -> None:
        self._http = http_client

    @staticmethod
    def _timespan(days: int) -> str:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return f"{start.strftime(fmt)}/{end.strftime(fmt)}"

    # ── public API ────────────────────────────────────────────────────────────

    def get_metric_average(
        self,
        resource_id: str,
        metric_name: str,
        days: int | None = None,
    ) -> float | None:
        """Return average of *metric_name* over *days* days, or None on failure."""
        lookback = days or get_settings().ANALYSIS_LOOKBACK_DAYS
        url = (
            f"{ARM_BASE}{resource_id}/providers/microsoft.insights/metrics"
            f"?api-version=2018-01-01&metricnames={metric_name}"
            f"&timespan={self._timespan(lookback)}&interval=P1D&aggregation=Average"
        )
        logger.debug("get_metric_average | metric=%s resource=…%s days=%d",
                     metric_name, resource_id[-40:], lookback)
        try:
            data = self._http.get(url)
            values = (
                data.get("value", [{}])[0]
                .get("timeseries", [{}])[0]
                .get("data", [])
            )
            avgs = [v["average"] for v in values if v.get("average") is not None]
            result = sum(avgs) / len(avgs) if avgs else None
            if result is None:
                logger.debug("No average data for metric=%s resource=…%s",
                             metric_name, resource_id[-40:])
            return result
        except AzureHttpStatusError as exc:
            if exc.status_code in (404, 400):
                logger.debug(
                    "Metric %s not available for resource=…%s (HTTP %s)",
                    metric_name, resource_id[-40:], exc.status_code,
                )
            else:
                logger.warning(
                    "Metric %s HTTP error for resource=…%s: %s",
                    metric_name, resource_id[-40:], exc,
                )
            return None
        except AzureHttpTimeoutError as exc:
            logger.warning("Metric %s timed out for resource=…%s: %s",
                           metric_name, resource_id[-40:], exc)
            return None
        except Exception as exc:
            logger.error("get_metric_average unexpected error | metric=%s resource=…%s: %s",
                         metric_name, resource_id[-40:], exc, exc_info=True)
            return None

    def get_metric_total(
        self,
        resource_id: str,
        metric_name: str,
        days: int | None = None,
    ) -> float | None:
        """Return sum of *metric_name* over *days* days, or None on failure."""
        lookback = days or get_settings().ANALYSIS_LOOKBACK_DAYS
        url = (
            f"{ARM_BASE}{resource_id}/providers/microsoft.insights/metrics"
            f"?api-version=2018-01-01&metricnames={metric_name}"
            f"&timespan={self._timespan(lookback)}&interval=P1D&aggregation=Total"
        )
        logger.debug("get_metric_total | metric=%s resource=…%s days=%d",
                     metric_name, resource_id[-40:], lookback)
        try:
            data = self._http.get(url)
            values = (
                data.get("value", [{}])[0]
                .get("timeseries", [{}])[0]
                .get("data", [])
            )
            totals = [v["total"] for v in values if v.get("total") is not None]
            return sum(totals) if totals else None
        except AzureHttpStatusError as exc:
            if exc.status_code in (404, 400):
                logger.debug("Metric %s not available for resource=…%s (HTTP %s)",
                             metric_name, resource_id[-40:], exc.status_code)
            else:
                logger.warning("Metric %s HTTP error for resource=…%s: %s",
                               metric_name, resource_id[-40:], exc)
            return None
        except AzureHttpTimeoutError as exc:
            logger.warning("Metric %s timed out for resource=…%s: %s",
                           metric_name, resource_id[-40:], exc)
            return None
        except Exception as exc:
            logger.error("get_metric_total unexpected error | metric=%s resource=…%s: %s",
                         metric_name, resource_id[-40:], exc, exc_info=True)
            return None

    def get_arm_resource(
        self,
        resource_id: str,
        api_version: str = "2021-04-01",
    ) -> dict | None:
        """Fetch ARM resource properties."""
        logger.debug("get_arm_resource | resource=…%s api_version=%s",
                     resource_id[-40:], api_version)
        try:
            return self._http.get(f"{ARM_BASE}{resource_id}?api-version={api_version}")
        except AzureHttpStatusError as exc:
            if exc.status_code == 404:
                logger.debug("ARM resource not found: …%s", resource_id[-40:])
            else:
                logger.warning("ARM resource fetch failed for …%s: HTTP %s",
                               resource_id[-40:], exc.status_code)
            return None
        except AzureHttpTimeoutError as exc:
            logger.warning("ARM resource fetch timed out for …%s: %s",
                           resource_id[-40:], exc)
            return None
        except Exception as exc:
            logger.error("get_arm_resource unexpected error for …%s: %s",
                         resource_id[-40:], exc, exc_info=True)
            return None

    def get_last_activity(
        self,
        resource_id: str,
        days: int = 30,
    ) -> datetime | None:
        """Return timestamp of most recent activity log entry for a resource."""
        sub_id = get_settings().AZURE_SUBSCRIPTION_ID
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        filter_str = (
            f"eventTimestamp ge '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'"
            f" and resourceId eq '{resource_id}'"
        )
        url = (
            f"{ARM_BASE}/subscriptions/{sub_id}"
            "/providers/microsoft.insights/eventtypes/management/values"
            f"?api-version=2015-04-01&$filter={filter_str}&$select=eventTimestamp"
        )
        logger.debug("get_last_activity | resource=…%s days=%d", resource_id[-40:], days)
        try:
            data = self._http.get(url)
            events = data.get("value", [])
            if not events:
                return None
            ts = events[0].get("eventTimestamp", "")
            return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
        except AzureHttpStatusError as exc:
            logger.warning("Activity log fetch failed for …%s: HTTP %s",
                           resource_id[-40:], exc.status_code)
            return None
        except Exception as exc:
            logger.error("get_last_activity unexpected error for …%s: %s",
                         resource_id[-40:], exc, exc_info=True)
            return None


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_metrics_service() -> MetricsService:
    client = AzureHttpClient(get_auth_service())
    return MetricsService(client)


def get_metric_average(resource_id: str, metric_name: str, days: int | None = None) -> float | None:
    return get_metrics_service().get_metric_average(resource_id, metric_name, days)


def get_metric_total(resource_id: str, metric_name: str, days: int | None = None) -> float | None:
    return get_metrics_service().get_metric_total(resource_id, metric_name, days)


def get_arm_resource(resource_id: str, api_version: str = "2021-04-01") -> dict | None:
    return get_metrics_service().get_arm_resource(resource_id, api_version)


def get_last_activity(resource_id: str, days: int = 30) -> datetime | None:
    return get_metrics_service().get_last_activity(resource_id, days)