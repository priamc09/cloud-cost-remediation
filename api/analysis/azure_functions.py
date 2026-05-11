"""IdleFunctionAppAnalyzer – 0 FunctionExecutionCount → idle_function_app."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleFunctionAppAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.web/sites"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        if not (resource.get("kind") or "").lower().startswith("functionapp"):
            return None
        cfg = get_settings()
        total = self._total(resource["resource_id"], "FunctionExecutionCount", days=cfg.ANALYSIS_LOOKBACK_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_function_app",
                severity="medium",
                reason=f"Function App had 0 executions over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None