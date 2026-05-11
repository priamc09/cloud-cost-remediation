"""IdleLogicAppAnalyzer – 0 RunsStarted → idle_logic_app."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleLogicAppAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.logic/workflows"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        total = self._total(resource["resource_id"], "RunsStarted", days=cfg.ANALYSIS_LOOKBACK_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_logic_app",
                severity="low",
                reason=f"Logic App had 0 runs over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None