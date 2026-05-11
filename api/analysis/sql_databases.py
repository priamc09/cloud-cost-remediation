"""IdleSQLDatabaseAnalyzer – 0 connection_successful → idle_sql_db."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleSQLDatabaseAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.sql/servers/databases"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        total = self._total(resource["resource_id"], "connection_successful", days=cfg.ANALYSIS_LOOKBACK_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="idle_sql_db",
                severity="high",
                reason=f"SQL Database had 0 successful connections over the last {cfg.ANALYSIS_LOOKBACK_DAYS} days.",
            )
        return None