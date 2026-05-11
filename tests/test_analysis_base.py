"""Unit tests for api.analysis.base — Finding, BaseAnalyzer, MetricAnalyzer, ArmPropertyAnalyzer."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from api.analysis.base import Finding, BaseAnalyzer, MetricAnalyzer, ArmPropertyAnalyzer


# ── Finding model ─────────────────────────────────────────────────────────────

def test_finding_fields():
    f = Finding(
        resource_id="/sub/rg/vm1",
        resource_name="vm1",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg1",
        location="eastus",
        finding_type="idle_vm",
        severity="high",
        reason="CPU low",
        estimated_monthly_cost_usd=42.5,
    )
    assert f.finding_type == "idle_vm"
    assert f.severity == "high"
    assert f.estimated_monthly_cost_usd == 42.5


def test_finding_is_frozen():
    """Finding is immutable (model_config frozen=True)."""
    f = Finding(
        resource_id="/sub/rg/vm1",
        resource_name="vm1",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg1",
        location="eastus",
        finding_type="idle_vm",
        severity="high",
        reason="CPU low",
    )
    with pytest.raises(Exception):
        f.finding_type = "other"  # type: ignore


def test_finding_default_cost():
    f = Finding(
        resource_id="/sub/rg/vm1",
        resource_name="vm1",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg1",
        location="eastus",
        finding_type="idle_vm",
        severity="low",
        reason="test",
    )
    assert f.estimated_monthly_cost_usd == 0.0


# ── Concrete BaseAnalyzer for testing ────────────────────────────────────────

class _AlwaysFindsAnalyzer(BaseAnalyzer):
    RESOURCE_TYPE = "microsoft.compute/virtualmachines"

    def _check(self, resource: dict, cost_map: dict) -> Finding | None:
        return Finding(
            resource_id=resource["resource_id"],
            resource_name=resource["name"],
            resource_type=resource["type"],
            resource_group=resource["resource_group"],
            location=resource["location"],
            finding_type="idle_vm",
            severity="high",
            reason="always",
        )


class _NeverFindsAnalyzer(BaseAnalyzer):
    RESOURCE_TYPE = "microsoft.compute/virtualmachines"

    def _check(self, resource: dict, cost_map: dict) -> Finding | None:
        return None


class _RaisesAnalyzer(BaseAnalyzer):
    RESOURCE_TYPE = "microsoft.compute/virtualmachines"

    def _check(self, resource: dict, cost_map: dict) -> Finding | None:
        raise ValueError("boom")


def _make_vm(rid="/sub/rg/providers/Microsoft.Compute/virtualMachines/vm1"):
    return {
        "resource_id": rid,
        "name": "vm1",
        "type": "microsoft.compute/virtualmachines",
        "resource_group": "rg1",
        "subscription_id": "sub",
        "location": "eastus",
        "tags": {},
        "sku": None,
        "kind": None,
    }


class TestBaseAnalyzer:
    def test_analyze_filters_by_type(self):
        analyzer = _AlwaysFindsAnalyzer()
        resources = [
            _make_vm(),
            {**_make_vm(), "type": "microsoft.compute/disks"},
        ]
        findings = analyzer.analyze(resources, {})
        assert len(findings) == 1
        assert findings[0].resource_type == "microsoft.compute/virtualmachines"

    def test_analyze_returns_findings(self):
        analyzer = _AlwaysFindsAnalyzer()
        findings = analyzer.analyze([_make_vm()], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_vm"

    def test_analyze_returns_empty_when_no_match(self):
        analyzer = _NeverFindsAnalyzer()
        findings = analyzer.analyze([_make_vm()], {})
        assert findings == []

    def test_analyze_skips_errors_gracefully(self):
        """Exceptions inside _check are caught; no finding emitted."""
        analyzer = _RaisesAnalyzer()
        findings = analyzer.analyze([_make_vm()], {})
        assert findings == []

    def test_analyze_empty_resource_list(self):
        analyzer = _AlwaysFindsAnalyzer()
        assert analyzer.analyze([], {}) == []

    def test_cost_helper_missing_key(self):
        analyzer = _AlwaysFindsAnalyzer()
        resource = _make_vm()
        assert analyzer._cost(resource, {}) == 0.0

    def test_cost_helper_present_key(self):
        analyzer = _AlwaysFindsAnalyzer()
        resource = _make_vm()
        cost_map = {resource["resource_id"].lower(): 99.9}
        assert analyzer._cost(resource, cost_map) == 99.9

    def test_finding_helper_builds_correctly(self):
        analyzer = _AlwaysFindsAnalyzer()
        resource = _make_vm()
        f = analyzer._finding(resource, {}, finding_type="idle_vm", severity="high", reason="test")
        assert f.resource_id == resource["resource_id"]
        assert f.resource_name == resource["name"]
        assert f.resource_group == resource["resource_group"]
        assert f.location == resource["location"]
        assert f.estimated_monthly_cost_usd == 0.0


# ── MetricAnalyzer ────────────────────────────────────────────────────────────

class TestMetricAnalyzer:
    def _make_analyzer(self, mock_svc):
        class Impl(MetricAnalyzer):
            RESOURCE_TYPE = "x"
            def _check(self, r, c):
                return None
        return Impl(mock_svc)

    def test_avg_delegates(self):
        mock_svc = MagicMock()
        mock_svc.get_metric_average.return_value = 3.5
        a = self._make_analyzer(mock_svc)
        result = a._avg("/sub/rg/vm1", "Percentage CPU")
        mock_svc.get_metric_average.assert_called_once_with("/sub/rg/vm1", "Percentage CPU", None)
        assert result == 3.5

    def test_total_delegates(self):
        mock_svc = MagicMock()
        mock_svc.get_metric_total.return_value = 100.0
        a = self._make_analyzer(mock_svc)
        result = a._total("/sub/rg/vm1", "Requests", days=7)
        mock_svc.get_metric_total.assert_called_once_with("/sub/rg/vm1", "Requests", 7)
        assert result == 100.0


# ── ArmPropertyAnalyzer ───────────────────────────────────────────────────────

class TestArmPropertyAnalyzer:
    def _make_analyzer(self, mock_svc):
        class Impl(ArmPropertyAnalyzer):
            RESOURCE_TYPE = "x"
            def _check(self, r, c):
                return None
        return Impl(mock_svc)

    def test_arm_delegates(self):
        mock_svc = MagicMock()
        mock_svc.get_arm_resource.return_value = {"id": "/sub/rg/disk1"}
        a = self._make_analyzer(mock_svc)
        result = a._arm("/sub/rg/disk1", api_version="2023-10-02")
        mock_svc.get_arm_resource.assert_called_once_with("/sub/rg/disk1", "2023-10-02")
        assert result == {"id": "/sub/rg/disk1"}

    def test_arm_returns_none_on_miss(self):
        mock_svc = MagicMock()
        mock_svc.get_arm_resource.return_value = None
        a = self._make_analyzer(mock_svc)
        assert a._arm("/sub/rg/disk1") is None
