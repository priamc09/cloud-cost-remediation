"""IdleAppServiceAnalyzer – 0 HTTP requests + not a function app → idle_app_service."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleAppServiceAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.web/sites"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        if (resource.get("kind") or "").lower().startswith("functionapp"):
            return None
        cfg = get_settings()
        total = self._total(resource["resource_id"], "Requests", days=cfg.ANALYSIS_LOOKBACK_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_app_service",
                severity="medium",
                reason=f"App Service received 0 HTTP requests over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None