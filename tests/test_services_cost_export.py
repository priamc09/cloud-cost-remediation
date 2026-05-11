"""Unit tests for CostExportService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from api.services.cost_export import CostExportService
from api.services.http_client import AzureHttpStatusError, AzureHttpClientError


def _make_service(http_mock=None):
    if http_mock is None:
        http_mock = MagicMock()
    return CostExportService(http_mock), http_mock


# ── _safe_float ───────────────────────────────────────────────────────────────

class TestSafeFloat:
    def test_valid_number(self):
        assert CostExportService._safe_float("12.34") == 12.34

    def test_integer_string(self):
        assert CostExportService._safe_float("100") == 100.0

    def test_number_with_comma(self):
        assert CostExportService._safe_float("1,234.56") == 1234.56

    def test_invalid_string_returns_zero(self):
        assert CostExportService._safe_float("N/A") == 0.0

    def test_empty_string_returns_zero(self):
        assert CostExportService._safe_float("") == 0.0

    def test_none_like_returns_zero(self):
        assert CostExportService._safe_float("null") == 0.0


# ── _parse_query_response ─────────────────────────────────────────────────────

class TestParseQueryResponse:
    def _response(self, columns, rows):
        return {
            "properties": {
                "columns": [{"name": c} for c in columns],
                "rows": rows,
            }
        }

    def test_basic_parse(self):
        data = self._response(
            ["Cost", "ResourceId", "ResourceType", "ResourceGroupName",
             "ServiceName", "MeterSubcategory", "ResourceLocation", "Currency"],
            [[50.0, "/sub/rg/providers/Microsoft.Compute/virtualMachines/vm1",
              "Microsoft.Compute/virtualMachines", "rg1", "Virtual Machines", "D2s v3",
              "eastus", "USD"]],
        )
        records = CostExportService._parse_query_response(data, "sub1")
        assert len(records) == 1
        assert records[0]["cost_usd"] == 50.0
        assert records[0]["resource_type"] == "Microsoft.Compute/virtualMachines"
        assert records[0]["resource_group"] == "rg1"
        assert records[0]["subscription_id"] == "sub1"

    def test_empty_columns_returns_empty(self):
        data = {"properties": {"columns": [], "rows": []}}
        records = CostExportService._parse_query_response(data, "sub1")
        assert records == []

    def test_properties_wrapper_handled(self):
        """Response wrapped inside 'properties' key should parse correctly."""
        data = {
            "properties": {
                "columns": [{"name": "Cost"}, {"name": "ResourceId"}],
                "rows": [[10.0, "/sub/rg/vm1"]],
            }
        }
        records = CostExportService._parse_query_response(data, "sub1")
        assert len(records) == 1
        assert records[0]["cost_usd"] == 10.0

    def test_direct_columns_without_properties_wrapper(self):
        """Response without 'properties' wrapper (some API versions)."""
        data = {
            "columns": [{"name": "Cost"}, {"name": "ResourceId"}],
            "rows": [[5.0, "/sub/rg/vm2"]],
        }
        records = CostExportService._parse_query_response(data, "sub1")
        assert len(records) == 1

    def test_missing_column_uses_default(self):
        data = self._response(
            ["Cost", "ResourceId"],
            [[99.0, "/sub/rg/vm1"]],
        )
        records = CostExportService._parse_query_response(data, "sub1")
        assert records[0]["currency"] == "USD"   # default fallback
        assert records[0]["service_name"] == ""

    def test_resource_id_lowercased(self):
        data = self._response(
            ["Cost", "ResourceId"],
            [[1.0, "/Sub/RG/Providers/Microsoft.Compute/VirtualMachines/VM1"]],
        )
        records = CostExportService._parse_query_response(data, "sub1")
        assert records[0]["resource_id"] == records[0]["resource_id"].lower()


# ── fetch_cost_by_resource ────────────────────────────────────────────────────

class TestFetchCostByResource:
    def _ok_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "properties": {
                "columns": [{"name": "Cost"}, {"name": "ResourceId"},
                             {"name": "ResourceType"}, {"name": "ResourceGroupName"},
                             {"name": "ServiceName"}, {"name": "MeterSubcategory"},
                             {"name": "ResourceLocation"}, {"name": "Currency"}],
                "rows": [[30.0, "/sub/rg/vm1", "Microsoft.Compute/virtualMachines",
                          "rg1", "Virtual Machines", "D2s v3", "eastus", "USD"]],
            }
        }
        return resp

    def test_200_response_returns_records(self):
        svc, http = _make_service()
        http.post.return_value = self._ok_response()
        records = svc.fetch_cost_by_resource()
        assert len(records) == 1
        assert records[0]["cost_usd"] == 30.0

    def test_http_status_error_raises(self):
        svc, http = _make_service()
        http.post.side_effect = AzureHttpStatusError("403", status_code=403)
        with pytest.raises(AzureHttpStatusError):
            svc.fetch_cost_by_resource()

    def test_network_error_raises(self):
        svc, http = _make_service()
        http.post.side_effect = AzureHttpClientError("timeout")
        with pytest.raises(AzureHttpClientError):
            svc.fetch_cost_by_resource()

    def test_non_json_body_returns_empty(self):
        svc, http = _make_service()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("not json")
        resp.text = "bad body"
        http.post.return_value = resp
        records = svc.fetch_cost_by_resource()
        assert records == []
