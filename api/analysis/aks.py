"""IdleAKSAnalyzer – node CPU avg < threshold → idle_aks."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleAKSAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.containerservice/managedclusters"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        avg_cpu = self._avg(resource["resource_id"], "node_cpu_usage_percentage")
        if avg_cpu is not None and avg_cpu < cfg.IDLE_AKS_CPU_THRESHOLD_PCT:
            return self._finding(
                resource, cost_map,
                finding_type="idle_aks",
                severity="high",
                reason=(
                    f"AKS cluster node CPU is {avg_cpu:.2f}% over {cfg.ANALYSIS_LOOKBACK_DAYS} days "
                    f"(threshold: {cfg.IDLE_AKS_CPU_THRESHOLD_PCT}%)."
                ),
            )
        return None