"""Unit tests for MetricsService."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from api.services.metrics import MetricsService
from api.services.http_client import AzureHttpStatusError, AzureHttpTimeoutError


def _make_svc():
    http = MagicMock()
    return MetricsService(http), http


def _metric_response(values: list[dict]) -> dict:
    """Build a minimal Azure Monitor metrics API response."""
    return {
        "value": [{
            "timeseries": [{
                "data": values,
            }]
        }]
    }


class TestGetMetricAverage:
    def test_returns_average(self):
        svc, http = _make_svc()
        http.get.return_value = _metric_response([
            {"average": 3.0},
            {"average": 7.0},
        ])
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result == 5.0

    def test_no_data_returns_none(self):
        svc, http = _make_svc()
        http.get.return_value = _metric_response([])
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_empty_response_returns_none(self):
        svc, http = _make_svc()
        http.get.return_value = {"value": []}
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_404_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpStatusError("Not found", status_code=404)
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_400_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpStatusError("Bad request", status_code=400)
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_timeout_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpTimeoutError("timeout")
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_unexpected_error_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = RuntimeError("boom")
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result is None

    def test_filters_out_none_averages(self):
        svc, http = _make_svc()
        http.get.return_value = _metric_response([
            {"average": 4.0},
            {},  # no average key
            {"average": 6.0},
        ])
        result = svc.get_metric_average("/sub/rg/vm1", "Percentage CPU")
        assert result == 5.0


class TestGetMetricTotal:
    def test_returns_sum(self):
        svc, http = _make_svc()
        http.get.return_value = _metric_response([
            {"total": 100.0},
            {"total": 200.0},
        ])
        result = svc.get_metric_total("/sub/rg/vm1", "Requests")
        assert result == 300.0

    def test_no_data_returns_none(self):
        svc, http = _make_svc()
        http.get.return_value = _metric_response([])
        result = svc.get_metric_total("/sub/rg/vm1", "Requests")
        assert result is None

    def test_404_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpStatusError("Not found", status_code=404)
        result = svc.get_metric_total("/sub/rg/vm1", "Requests")
        assert result is None

    def test_timeout_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpTimeoutError("timeout")
        result = svc.get_metric_total("/sub/rg/vm1", "Requests")
        assert result is None


class TestGetArmResource:
    def test_success_returns_data(self):
        svc, http = _make_svc()
        http.get.return_value = {"id": "/sub/rg/disk1", "properties": {"diskState": "Attached"}}
        result = svc.get_arm_resource("/sub/rg/disk1")
        assert result["properties"]["diskState"] == "Attached"

    def test_404_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpStatusError("Not found", status_code=404)
        result = svc.get_arm_resource("/sub/rg/disk1")
        assert result is None

    def test_timeout_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpTimeoutError("timeout")
        result = svc.get_arm_resource("/sub/rg/disk1")
        assert result is None

    def test_other_http_error_returns_none(self):
        svc, http = _make_svc()
        http.get.side_effect = AzureHttpStatusError("Server error", status_code=500)
        result = svc.get_arm_resource("/sub/rg/disk1")
        assert result is None
