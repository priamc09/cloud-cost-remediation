"""
AnalysisPipeline – orchestrates all registered analyzers.

All concrete BaseAnalyzer subclasses are registered in REGISTRY.
Each requires a MetricsService injected at construction so the
pipeline can be tested with mock services.

Public API
──────────
build_pipeline(metrics_service) → AnalysisPipeline
run_all(resources, cost_map)    → list[Finding]   (uses process singleton)
"""
from __future__ import annotations

import logging
from functools import lru_cache

from api.analysis.base import BaseAnalyzer, Finding
from api.analysis.virtual_machines import IdleVMAnalyzer
from api.analysis.managed_disks import OrphanDiskAnalyzer
from api.analysis.storage_accounts import ColdStorageAnalyzer
from api.analysis.app_services import IdleAppServiceAnalyzer
from api.analysis.azure_functions import IdleFunctionAppAnalyzer
from api.analysis.logic_apps import IdleLogicAppAnalyzer
from api.analysis.adf_pipelines import IdleADFAnalyzer
from api.analysis.sql_databases import IdleSQLDatabaseAnalyzer
from api.analysis.cosmos_db import IdleCosmosDBAnalyzer
from api.analysis.aks import IdleAKSAnalyzer

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Runs every registered analyzer and aggregates findings.

    Metric-based analyzers receive the shared MetricsService.
    ADF uses its own HTTP client (injected at construction).
    """

    def __init__(self, metrics_service) -> None:
        # Metric-based analyzers
        metric_analyzers: list[BaseAnalyzer] = [
            IdleVMAnalyzer(metrics_service),
            ColdStorageAnalyzer(metrics_service),
            IdleAppServiceAnalyzer(metrics_service),
            IdleFunctionAppAnalyzer(metrics_service),
            IdleLogicAppAnalyzer(metrics_service),
            IdleSQLDatabaseAnalyzer(metrics_service),
            IdleCosmosDBAnalyzer(metrics_service),
            IdleAKSAnalyzer(metrics_service),
            # ARM-property based
            OrphanDiskAnalyzer(metrics_service),
        ]
        # ADF uses its own HTTP client
        other_analyzers: list[BaseAnalyzer] = [
            IdleADFAnalyzer(),
        ]
        self._analyzers: list[BaseAnalyzer] = metric_analyzers + other_analyzers

    def run(
        self,
        resources: list[dict],
        cost_map: dict[str, float],
    ) -> list[Finding]:
        """Run all analyzers; return aggregated, deduplicated findings."""
        all_findings: list[Finding] = []
        seen: set[str] = set()
        for analyzer in self._analyzers:
            for finding in analyzer.analyze(resources, cost_map):
                key = f"{finding.resource_id}::{finding.finding_type}"
                if key not in seen:
                    seen.add(key)
                    all_findings.append(finding)
        logger.info("[pipeline] %d total findings from %d analyzers", len(all_findings), len(self._analyzers))
        return all_findings


# ── Process-wide singleton ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_pipeline() -> AnalysisPipeline:
    from api.services.metrics import get_metrics_service
    return AnalysisPipeline(get_metrics_service())


# ── Module-level shim (backward compat) ──────────────────────────────────────

def run_all(resources: list[dict], cost_map: dict[str, float]) -> list[Finding]:
    return _get_pipeline().run(resources, cost_map)