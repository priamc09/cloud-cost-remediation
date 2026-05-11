"""IdleVMAnalyzer – CPU avg < threshold → idle_vm finding."""
from __future__ import annotations
from api.analysis.base import Finding, MetricAnalyzer
from api.config import get_settings


class IdleVMAnalyzer(MetricAnalyzer):
    RESOURCE_TYPE = "microsoft.compute/virtualmachines"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        cfg = get_settings()
        avg_cpu = self._avg(resource["resource_id"], "Percentage CPU")
        if avg_cpu is not None and avg_cpu < cfg.IDLE_VM_CPU_THRESHOLD_PCT:
            return self._finding(
                resource, cost_map,
                finding_type="idle_vm",
                severity="high",
                reason=(
                    f"VM average CPU is {avg_cpu:.2f}% over {cfg.ANALYSIS_LOOKBACK_DAYS} days "
                    f"(threshold: {cfg.IDLE_VM_CPU_THRESHOLD_PCT}%)."
                ),
            )
        return None