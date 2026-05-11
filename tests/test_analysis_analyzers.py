"""Unit tests for all 10 concrete analyzer implementations."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from api.analysis.virtual_machines import IdleVMAnalyzer
from api.analysis.managed_disks import OrphanDiskAnalyzer
from api.analysis.storage_accounts import ColdStorageAnalyzer
from api.analysis.app_services import IdleAppServiceAnalyzer
from api.analysis.azure_functions import IdleFunctionAppAnalyzer
from api.analysis.logic_apps import IdleLogicAppAnalyzer
from api.analysis.sql_databases import IdleSQLDatabaseAnalyzer
from api.analysis.cosmos_db import IdleCosmosDBAnalyzer
from api.analysis.aks import IdleAKSAnalyzer
from api.analysis.adf_pipelines import IdleADFAnalyzer
from api.services.http_client import AzureHttpClientError, AzureHttpStatusError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resource(rtype: str, name: str = "res1", kind: str | None = None) -> dict:
    return {
        "resource_id": f"/subscriptions/sub/resourceGroups/rg1/providers/{rtype}/{name}",
        "name": name,
        "type": rtype.lower(),
        "resource_group": "rg1",
        "subscription_id": "sub",
        "location": "eastus",
        "tags": {},
        "sku": None,
        "kind": kind,
    }


def _mock_metrics(avg=None, total=None, arm=None):
    m = MagicMock()
    m.get_metric_average.return_value = avg
    m.get_metric_total.return_value = total
    m.get_arm_resource.return_value = arm
    return m


# ── IdleVMAnalyzer ────────────────────────────────────────────────────────────

class TestIdleVMAnalyzer:
    VM_TYPE = "microsoft.compute/virtualmachines"

    def test_low_cpu_produces_finding(self):
        svc = _mock_metrics(avg=2.0)
        analyzer = IdleVMAnalyzer(svc)
        res = _resource(self.VM_TYPE)
        findings = analyzer.analyze([res], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_vm"
        assert findings[0].severity == "high"

    def test_cpu_above_threshold_no_finding(self):
        svc = _mock_metrics(avg=20.0)
        analyzer = IdleVMAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.VM_TYPE)], {})
        assert findings == []

    def test_no_metric_data_no_finding(self):
        svc = _mock_metrics(avg=None)
        analyzer = IdleVMAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.VM_TYPE)], {})
        assert findings == []

    def test_cost_included_in_finding(self):
        svc = _mock_metrics(avg=1.0)
        analyzer = IdleVMAnalyzer(svc)
        res = _resource(self.VM_TYPE)
        cost_map = {res["resource_id"].lower(): 150.0}
        findings = analyzer.analyze([res], cost_map)
        assert findings[0].estimated_monthly_cost_usd == 150.0

    def test_wrong_resource_type_skipped(self):
        svc = _mock_metrics(avg=1.0)
        analyzer = IdleVMAnalyzer(svc)
        findings = analyzer.analyze([_resource("microsoft.compute/disks")], {})
        assert findings == []

    def test_exactly_at_threshold_no_finding(self):
        """CPU exactly at threshold (5.0) should NOT trigger."""
        svc = _mock_metrics(avg=5.0)
        analyzer = IdleVMAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.VM_TYPE)], {})
        assert findings == []


# ── OrphanDiskAnalyzer ────────────────────────────────────────────────────────

class TestOrphanDiskAnalyzer:
    DISK_TYPE = "microsoft.compute/disks"

    def test_unattached_disk_finding(self):
        arm_data = {"properties": {"diskState": "Unattached"}}
        svc = _mock_metrics(arm=arm_data)
        analyzer = OrphanDiskAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.DISK_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "orphan_disk"
        assert findings[0].severity == "medium"

    def test_attached_disk_no_finding(self):
        arm_data = {"properties": {"diskState": "Attached"}}
        svc = _mock_metrics(arm=arm_data)
        analyzer = OrphanDiskAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.DISK_TYPE)], {})
        assert findings == []

    def test_arm_returns_none_no_finding(self):
        svc = _mock_metrics(arm=None)
        analyzer = OrphanDiskAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.DISK_TYPE)], {})
        assert findings == []

    def test_case_insensitive_disk_state(self):
        arm_data = {"properties": {"diskState": "UNATTACHED"}}
        svc = _mock_metrics(arm=arm_data)
        analyzer = OrphanDiskAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.DISK_TYPE)], {})
        assert len(findings) == 1


# ── ColdStorageAnalyzer ───────────────────────────────────────────────────────

class TestColdStorageAnalyzer:
    STORAGE_TYPE = "microsoft.storage/storageaccounts"

    def test_zero_transactions_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = ColdStorageAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.STORAGE_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "cold_storage"

    def test_nonzero_transactions_no_finding(self):
        svc = _mock_metrics(total=500.0)
        analyzer = ColdStorageAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.STORAGE_TYPE)], {})
        assert findings == []

    def test_none_metric_no_finding(self):
        svc = _mock_metrics(total=None)
        analyzer = ColdStorageAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.STORAGE_TYPE)], {})
        assert findings == []


# ── IdleAppServiceAnalyzer ────────────────────────────────────────────────────

class TestIdleAppServiceAnalyzer:
    APP_TYPE = "microsoft.web/sites"

    def test_zero_requests_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleAppServiceAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.APP_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_app_service"

    def test_function_app_kind_skipped(self):
        """FunctionApp kind should be skipped by IdleAppServiceAnalyzer."""
        svc = _mock_metrics(total=0.0)
        analyzer = IdleAppServiceAnalyzer(svc)
        res = _resource(self.APP_TYPE, kind="functionapp,linux")
        findings = analyzer.analyze([res], {})
        assert findings == []

    def test_nonzero_requests_no_finding(self):
        svc = _mock_metrics(total=100.0)
        analyzer = IdleAppServiceAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.APP_TYPE)], {})
        assert findings == []

    def test_none_requests_no_finding(self):
        svc = _mock_metrics(total=None)
        analyzer = IdleAppServiceAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.APP_TYPE)], {})
        assert findings == []


# ── IdleFunctionAppAnalyzer ───────────────────────────────────────────────────

class TestIdleFunctionAppAnalyzer:
    APP_TYPE = "microsoft.web/sites"

    def test_function_app_zero_executions_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleFunctionAppAnalyzer(svc)
        res = _resource(self.APP_TYPE, kind="functionapp")
        findings = analyzer.analyze([res], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_function_app"

    def test_regular_app_skipped(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleFunctionAppAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.APP_TYPE)], {})
        assert findings == []

    def test_function_app_with_executions_no_finding(self):
        svc = _mock_metrics(total=50.0)
        analyzer = IdleFunctionAppAnalyzer(svc)
        res = _resource(self.APP_TYPE, kind="functionapp")
        findings = analyzer.analyze([res], {})
        assert findings == []


# ── IdleLogicAppAnalyzer ──────────────────────────────────────────────────────

class TestIdleLogicAppAnalyzer:
    LOGIC_TYPE = "microsoft.logic/workflows"

    def test_zero_runs_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleLogicAppAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.LOGIC_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_logic_app"
        assert findings[0].severity == "low"

    def test_nonzero_runs_no_finding(self):
        svc = _mock_metrics(total=5.0)
        analyzer = IdleLogicAppAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.LOGIC_TYPE)], {})
        assert findings == []


# ── IdleSQLDatabaseAnalyzer ───────────────────────────────────────────────────

class TestIdleSQLDatabaseAnalyzer:
    SQL_TYPE = "microsoft.sql/servers/databases"

    def test_zero_connections_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleSQLDatabaseAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.SQL_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_sql_db"
        assert findings[0].severity == "high"

    def test_with_connections_no_finding(self):
        svc = _mock_metrics(total=10.0)
        analyzer = IdleSQLDatabaseAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.SQL_TYPE)], {})
        assert findings == []


# ── IdleCosmosDBAnalyzer ──────────────────────────────────────────────────────

class TestIdleCosmosDBAnalyzer:
    COSMOS_TYPE = "microsoft.documentdb/databaseaccounts"

    def test_zero_requests_finding(self):
        svc = _mock_metrics(total=0.0)
        analyzer = IdleCosmosDBAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.COSMOS_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_cosmos_db"
        assert findings[0].severity == "high"

    def test_with_requests_no_finding(self):
        svc = _mock_metrics(total=1000.0)
        analyzer = IdleCosmosDBAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.COSMOS_TYPE)], {})
        assert findings == []


# ── IdleAKSAnalyzer ───────────────────────────────────────────────────────────

class TestIdleAKSAnalyzer:
    AKS_TYPE = "microsoft.containerservice/managedclusters"

    def test_low_cpu_finding(self):
        svc = _mock_metrics(avg=3.0)
        analyzer = IdleAKSAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.AKS_TYPE)], {})
        assert len(findings) == 1
        assert findings[0].finding_type == "idle_aks"
        assert findings[0].severity == "high"

    def test_high_cpu_no_finding(self):
        svc = _mock_metrics(avg=50.0)
        analyzer = IdleAKSAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.AKS_TYPE)], {})
        assert findings == []

    def test_no_metric_no_finding(self):
        svc = _mock_metrics(avg=None)
        analyzer = IdleAKSAnalyzer(svc)
        findings = analyzer.analyze([_resource(self.AKS_TYPE)], {})
        assert findings == []


# ── IdleADFAnalyzer ───────────────────────────────────────────────────────────

class TestIdleADFAnalyzer:
    ADF_TYPE = "microsoft.datafactory/factories"

    def _make_mock_http(self, runs: list) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = {"value": runs}
        mock_http = MagicMock()
        mock_http.post.return_value = resp
        return mock_http

    def test_zero_runs_produces_finding(self):
        with patch("api.analysis.adf_pipelines.AzureHttpClient") as MockClient, \
             patch("api.analysis.adf_pipelines.get_auth_service"):
            MockClient.return_value = self._make_mock_http([])
            analyzer = IdleADFAnalyzer()
            res = _resource(self.ADF_TYPE)
            findings = analyzer.analyze([res], {})
            assert len(findings) == 1
            assert findings[0].finding_type == "idle_adf"

    def test_with_runs_no_finding(self):
        with patch("api.analysis.adf_pipelines.AzureHttpClient") as MockClient, \
             patch("api.analysis.adf_pipelines.get_auth_service"):
            MockClient.return_value = self._make_mock_http([{"runId": "abc"}])
            analyzer = IdleADFAnalyzer()
            res = _resource(self.ADF_TYPE)
            findings = analyzer.analyze([res], {})
            assert findings == []

    def test_http_status_error_returns_none(self):
        with patch("api.analysis.adf_pipelines.AzureHttpClient") as MockClient, \
             patch("api.analysis.adf_pipelines.get_auth_service"):
            mock_http = MagicMock()
            mock_http.post.side_effect = AzureHttpStatusError("403", status_code=403)
            MockClient.return_value = mock_http
            analyzer = IdleADFAnalyzer()
            res = _resource(self.ADF_TYPE)
            findings = analyzer.analyze([res], {})
            assert findings == []

    def test_network_error_returns_none(self):
        with patch("api.analysis.adf_pipelines.AzureHttpClient") as MockClient, \
             patch("api.analysis.adf_pipelines.get_auth_service"):
            mock_http = MagicMock()
            mock_http.post.side_effect = AzureHttpClientError("timeout")
            MockClient.return_value = mock_http
            analyzer = IdleADFAnalyzer()
            res = _resource(self.ADF_TYPE)
            findings = analyzer.analyze([res], {})
            assert findings == []
