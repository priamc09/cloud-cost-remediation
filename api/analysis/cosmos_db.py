"""IdleCosmosDBAnalyzer – 0 TotalRequestUnits → idle_cosmos_db."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleCosmosDBAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.documentdb/databaseaccounts"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        total = self._total(resource["resource_id"], "TotalRequestUnits", days=cfg.ANALYSIS_LOOKBACK_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_cosmos_db",
                severity="high",
                reason=f"Cosmos DB had 0 request units consumed over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None