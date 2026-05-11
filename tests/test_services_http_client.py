"""Tests for AzureHttpClient."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
import httpx

from api.services.http_client import (
    AzureHttpClient,
    AzureHttpClientError,
    AzureHttpStatusError,
    AzureHttpTimeoutError,
)


def _make_client(token="fake-token"):
    """Return AzureHttpClient with a mocked auth service."""
    mock_auth = MagicMock()
    mock_auth.auth_headers.return_value = {"Authorization": f"Bearer {token}"}
    return AzureHttpClient(auth_service=mock_auth)


def _mock_response(status=200, json_body=None, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    resp.json.return_value = json_body or {}
    resp.text = text
    resp.content = text.encode() if text else b""
    return resp


class TestAzureHttpClientGet:
    def test_successful_get_returns_json(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(200, {"key": "val"})):
            result = client.get("https://management.azure.com/test")
        assert result == {"key": "val"}

    def test_404_raises_status_error(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(404, text="not found")):
            with pytest.raises(AzureHttpStatusError) as exc_info:
                client.get("https://management.azure.com/test")
        assert exc_info.value.status_code == 404

    def test_500_raises_status_error(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(500, text="server error")):
            with pytest.raises(AzureHttpStatusError) as exc_info:
                client.get("https://management.azure.com/test")
        assert exc_info.value.status_code == 500

    def test_timeout_raises_timeout_error(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(AzureHttpTimeoutError):
                client.get("https://management.azure.com/test")

    def test_network_error_raises_client_error(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            with pytest.raises(AzureHttpClientError):
                client.get("https://management.azure.com/test")


class TestAzureHttpClientPost:
    def test_successful_post_returns_response(self):
        client = _make_client()
        mock_resp = _mock_response(200)
        with patch("httpx.post", return_value=mock_resp):
            result = client.post("https://management.azure.com/test", json={"a": 1})
        assert result is mock_resp

    def test_post_timeout_raises(self):
        client = _make_client()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(AzureHttpTimeoutError):
                client.post("https://management.azure.com/test")

    def test_post_network_error_raises(self):
        client = _make_client()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(AzureHttpClientError):
                client.post("https://management.azure.com/test")


class TestAzureHttpClientRaw:
    def test_get_raw_auth_returns_response(self):
        client = _make_client()
        mock_resp = _mock_response(202, text="")
        with patch("httpx.get", return_value=mock_resp):
            result = client.get_raw_auth("https://management.azure.com/poll")
        assert result is mock_resp

    def test_get_raw_auth_timeout_raises(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.TimeoutException("t")):
            with pytest.raises(AzureHttpTimeoutError):
                client.get_raw_auth("https://management.azure.com/poll")

    def test_get_raw_auth_network_error_raises(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.ConnectError("e")):
            with pytest.raises(AzureHttpClientError):
                client.get_raw_auth("https://management.azure.com/poll")

    def test_get_raw_returns_response(self):
        client = _make_client()
        mock_resp = _mock_response(200, text="blob content")
        with patch("httpx.get", return_value=mock_resp):
            result = client.get_raw("https://blob.storage.example.com/file?sas=token")
        assert result is mock_resp

    def test_get_raw_non_2xx_raises_status_error(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(403, text="forbidden")):
            with pytest.raises(AzureHttpStatusError) as exc_info:
                client.get_raw("https://blob.storage.example.com/file")
        assert exc_info.value.status_code == 403

    def test_get_raw_timeout_raises(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.TimeoutException("t")):
            with pytest.raises(AzureHttpTimeoutError):
                client.get_raw("https://blob.storage.example.com/file")

    def test_get_raw_network_error_raises(self):
        client = _make_client()
        with patch("httpx.get", side_effect=httpx.ConnectError("e")):
            with pytest.raises(AzureHttpClientError):
                client.get_raw("https://blob.storage.example.com/file")


class TestShortAndCheck:
    def test_short_strips_sas_query(self):
        url = "https://blob.core.windows.net/file?sv=2023&sig=abc123"
        result = AzureHttpClient._short(url)
        assert result.endswith("?…")
        assert "sig=abc" not in result

    def test_short_no_query(self):
        url = "https://management.azure.com/subscriptions/abc"
        result = AzureHttpClient._short(url)
        assert result == url
