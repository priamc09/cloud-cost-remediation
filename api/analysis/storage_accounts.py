"""ColdStorageAnalyzer – zero Transactions → cold_storage finding."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class ColdStorageAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.storage/storageaccounts"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        total = self._total(resource["resource_id"], "Transactions", days=cfg.IDLE_STORAGE_DAYS)
        if total is not None and total == 0:
            return self._finding(
                resource, cost_map,
                finding_type="cold_storage",
                severity="medium",
                reason=f"Storage account has 0 transactions over the last {cfg.IDLE_STORAGE_DAYS} days.",
            )
        return None