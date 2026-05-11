"""IdleADFAnalyzer – no pipeline runs in lookback window → idle_adf."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from api.analysis.base import BaseAnalyzer, Finding
from api.config import get_settings
from api.services.azure_auth import get_auth_service
from api.services.http_client import AzureHttpClient, AzureHttpClientError, AzureHttpStatusError

logger = logging.getLogger(__name__)

ARM_BASE = "https://management.azure.com"
ADF_API = "2018-06-01"


class IdleADFAnalyzer(BaseAnalyzer):
    """
    ADF uses a dedicated queryPipelineRuns API, not Azure Monitor metrics,
    so this class extends BaseAnalyzer directly and builds its own HTTP client.
    """
    RESOURCE_TYPE = "microsoft.datafactory/factories"

    def __init__(self) -> None:
        self._http = AzureHttpClient(get_auth_service())

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=cfg.ANALYSIS_LOOKBACK_DAYS)

        url = (
            f"{ARM_BASE}{resource['resource_id']}"
            f"/queryPipelineRuns?api-version={ADF_API}"
        )
        body = {
            "lastUpdatedAfter": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lastUpdatedBefore": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            resp = self._http.post(url, json=body)
            runs = resp.json().get("value", [])
        except AzureHttpStatusError as exc:
            logger.warning(
                "ADF pipeline query HTTP error for %s: status=%s",
                resource["resource_id"], exc.status_code,
            )
            return None
        except AzureHttpClientError as exc:
            logger.warning(
                "ADF pipeline query network error for %s: %s",
                resource["resource_id"], exc,
            )
            return None
        except Exception as exc:
            logger.error(
                "ADF pipeline query unexpected error for %s: %s",
                resource["resource_id"], exc, exc_info=True,
            )
            return None

        if len(runs) == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_adf",
                severity="medium",
                reason=f"Azure Data Factory had 0 pipeline runs over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None