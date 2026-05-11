"""Unit tests for ResourceExportService."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from api.services.resource_export import ResourceExportService
from api.services.http_client import AzureHttpStatusError, AzureHttpClientError


def _make_service():
    http = MagicMock()
    return ResourceExportService(http), http


def _arg_item(name="vm1", rtype="microsoft.compute/virtualmachines"):
    return {
        "id": f"/subscriptions/sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/{name}",
        "name": name,
        "type": rtype,
        "resourceGroup": "rg1",
        "subscriptionId": "sub",
        "location": "eastus",
        "tags": {},
        "sku": None,
        "kind": None,
    }


def _arg_response(items, skip_token=None):
    resp = MagicMock()
    data = {"data": items}
    if skip_token:
        data["$skipToken"] = skip_token
    resp.json.return_value = data
    return resp


def _arm_response(items, next_link=None):
    data = {"value": items}
    if next_link:
        data["nextLink"] = next_link
    return data


class TestResourceExportService:
    def test_fetch_via_arg_single_page(self):
        svc, http = _make_service()
        http.post.return_value = _arg_response([_arg_item()])
        resources = svc._fetch_via_resource_graph("sub")
        assert len(resources) == 1
        assert resources[0]["name"] == "vm1"

    def test_fetch_via_arg_pagination(self):
        svc, http = _make_service()
        page1 = _arg_response([_arg_item("vm1")], skip_token="token123")
        page2 = _arg_response([_arg_item("vm2")])
        http.post.side_effect = [page1, page2]
        resources = svc._fetch_via_resource_graph("sub")
        assert len(resources) == 2

    def test_fetch_via_arg_empty_stops(self):
        svc, http = _make_service()
        http.post.return_value = _arg_response([])
        resources = svc._fetch_via_resource_graph("sub")
        assert resources == []

    def test_fetch_via_arm_list_single_page(self):
        svc, http = _make_service()
        http.get.return_value = _arm_response([_arg_item()])
        resources = svc._fetch_via_arm_list("sub")
        assert len(resources) == 1

    def test_fetch_via_arm_list_pagination(self):
        svc, http = _make_service()
        page1 = _arm_response([_arg_item("vm1")], next_link="https://next")
        page2 = _arm_response([_arg_item("vm2")])
        http.get.side_effect = [page1, page2]
        resources = svc._fetch_via_arm_list("sub")
        assert len(resources) == 2

    def test_fetch_all_falls_back_to_arm_on_arg_empty(self):
        """If ARG returns 0 resources, fall back to ARM list."""
        svc, http = _make_service()
        # ARG returns empty
        http.post.return_value = _arg_response([])
        # ARM returns 1
        http.get.return_value = _arm_response([_arg_item()])
        resources = svc.fetch_all()
        assert len(resources) == 1

    def test_fetch_all_falls_back_to_arm_on_arg_exception(self):
        """If ARG raises, fall back to ARM list."""
        svc, http = _make_service()
        http.post.side_effect = AzureHttpStatusError("500", status_code=500)
        http.get.return_value = _arm_response([_arg_item()])
        resources = svc.fetch_all()
        assert len(resources) == 1

    def test_fetch_all_arg_success(self):
        svc, http = _make_service()
        http.post.return_value = _arg_response([_arg_item("vm1"), _arg_item("vm2")])
        resources = svc.fetch_all()
        assert len(resources) == 2
        http.get.assert_not_called()
