"""
Analysis base layer.

Hierarchy
─────────
Finding                        – Pydantic model representing one detected issue
BaseAnalyzer (ABC)             – contract every analyzer must satisfy
  ├─ MetricAnalyzer            – helper base for Azure Monitor metric-based checks
  └─ ArmPropertyAnalyzer       – helper base for ARM property-based checks
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── Value object ──────────────────────────────────────────────────────────────

class Finding(BaseModel):
    """Immutable value object emitted by each analyzer."""
    resource_id: str
    resource_name: str
    resource_type: str
    resource_group: str
    location: str
    finding_type: str       # e.g. idle_vm | orphan_disk | cold_storage
    severity: str           # high | medium | low
    reason: str
    estimated_monthly_cost_usd: float = 0.0

    model_config = {"frozen": True}


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseAnalyzer(ABC):
    """
    Contract for all analyzers.

    Subclasses MUST declare:
        RESOURCE_TYPE: ClassVar[str]   – lower-case ARM type string

    Subclasses MUST implement:
        _check(resource, cost_map) -> Finding | None
    """

    RESOURCE_TYPE: ClassVar[str]

    def analyze(
        self,
        resources: list[dict],
        cost_map: dict[str, float],
    ) -> list[Finding]:
        """Filter to this type, run _check on each, return non-None results."""
        relevant = [
            r for r in resources
            if r.get("type", "").lower() == self.RESOURCE_TYPE
        ]
        findings: list[Finding] = []
        for resource in relevant:
            try:
                finding = self._check(resource, cost_map)
                if finding is not None:
                    findings.append(finding)
            except Exception as exc:
                logger.warning(
                    "[%s] error analysing %s: %s",
                    self.__class__.__name__,
                    resource.get("resource_id", "?"),
                    exc,
                )
        return findings

    @abstractmethod
    def _check(
        self,
        resource: dict,
        cost_map: dict[str, float],
    ) -> Finding | None:
        """Return a Finding if the resource is wasteful, else None."""

    # ── shared helpers ────────────────────────────────────────────────────────

    def _cost(self, resource: dict, cost_map: dict[str, float]) -> float:
        return cost_map.get(resource["resource_id"].lower(), 0.0)

    def _finding(self, resource: dict, cost_map: dict[str, float], **kwargs) -> Finding:
        """Build a Finding pre-filled with resource identity fields."""
        return Finding(
            resource_id=resource["resource_id"],
            resource_name=resource["name"],
            resource_type=resource["type"],
            resource_group=resource["resource_group"],
            location=resource["location"],
            estimated_monthly_cost_usd=self._cost(resource, cost_map),
            **kwargs,
        )


# ── Intermediate: metric-based ────────────────────────────────────────────────

class MetricAnalyzer(BaseAnalyzer, ABC):
    """Base for analyzers using Azure Monitor metrics. Accepts injected MetricsService."""

    def __init__(self, metrics_service) -> None:
        self._metrics = metrics_service

    def _avg(self, resource_id: str, metric: str, days: int | None = None) -> float | None:
        return self._metrics.get_metric_average(resource_id, metric, days)

    def _total(self, resource_id: str, metric: str, days: int | None = None) -> float | None:
        return self._metrics.get_metric_total(resource_id, metric, days)


# ── Intermediate: ARM-property-based ─────────────────────────────────────────

class ArmPropertyAnalyzer(BaseAnalyzer, ABC):
    """Base for analyzers that inspect ARM resource properties."""

    def __init__(self, metrics_service) -> None:
        self._metrics = metrics_service

    def _arm(self, resource_id: str, api_version: str = "2021-04-01") -> dict | None:
        return self._metrics.get_arm_resource(resource_id, api_version)