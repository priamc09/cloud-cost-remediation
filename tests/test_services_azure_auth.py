"""Tests for AzureAuthService."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


def _make_service():
    """Return AzureAuthService with all Azure SDK calls mocked."""
    with patch("api.services.azure_auth.ClientSecretCredential") as MockCred:
        mock_cred_instance = MagicMock()
        MockCred.return_value = mock_cred_instance
        from api.services.azure_auth import AzureAuthService
        svc = AzureAuthService()
        svc._credential = mock_cred_instance
    return svc


class TestAzureAuthService:
    def test_get_token_returns_string(self):
        svc = _make_service()
        svc._credential.get_token.return_value = MagicMock(token="test-bearer-token")
        token = svc.get_token("https://management.azure.com/.default")
        assert token == "test-bearer-token"

    def test_auth_headers_returns_bearer(self):
        svc = _make_service()
        svc._credential.get_token.return_value = MagicMock(token="mytoken")
        headers = svc.auth_headers()
        assert headers == {"Authorization": "Bearer mytoken"}

    def test_get_token_client_auth_error_propagates(self):
        from azure.core.exceptions import ClientAuthenticationError
        svc = _make_service()
        svc._credential.get_token.side_effect = ClientAuthenticationError("bad creds")
        with pytest.raises(ClientAuthenticationError):
            svc.get_token()

    def test_get_token_unexpected_error_propagates(self):
        svc = _make_service()
        svc._credential.get_token.side_effect = RuntimeError("unexpected")
        with pytest.raises(RuntimeError):
            svc.get_token()

    def test_get_kv_secret_returns_value(self):
        svc = _make_service()
        mock_client = MagicMock()
        mock_client.get_secret.return_value.value = "mysecret"
        with patch("api.services.azure_auth.SecretClient", return_value=mock_client):
            result = svc.get_kv_secret("my-secret-name")
        assert result == "mysecret"

    def test_get_kv_secret_http_error_propagates(self):
        from azure.core.exceptions import HttpResponseError
        svc = _make_service()
        mock_client = MagicMock()
        err = HttpResponseError("vault error")
        err.status_code = 403
        err.message = "Forbidden"
        mock_client.get_secret.side_effect = err
        with patch("api.services.azure_auth.SecretClient", return_value=mock_client):
            with pytest.raises(HttpResponseError):
                svc.get_kv_secret("my-secret-name")

    def test_get_kv_secret_unexpected_error_propagates(self):
        svc = _make_service()
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = ConnectionError("vault unreachable")
        with patch("api.services.azure_auth.SecretClient", return_value=mock_client):
            with pytest.raises(ConnectionError):
                svc.get_kv_secret("my-secret-name")

    def test_init_credential_error_raises(self):
        with patch("api.services.azure_auth.ClientSecretCredential",
                   side_effect=ValueError("bad params")):
            from api.services.azure_auth import AzureAuthService
            with pytest.raises(ValueError):
                AzureAuthService()


class TestModuleLevelShims:
    def test_get_token_shim(self):
        from api.services import azure_auth
        mock_svc = MagicMock()
        mock_svc.get_token.return_value = "shim-token"
        with patch("api.services.azure_auth.get_auth_service", return_value=mock_svc):
            result = azure_auth.get_token("https://management.azure.com/.default")
        assert result == "shim-token"

    def test_auth_headers_shim(self):
        from api.services import azure_auth
        mock_svc = MagicMock()
        mock_svc.auth_headers.return_value = {"Authorization": "Bearer x"}
        with patch("api.services.azure_auth.get_auth_service", return_value=mock_svc):
            result = azure_auth.auth_headers()
        assert "Authorization" in result

    def test_get_kv_secret_shim(self):
        from api.services import azure_auth
        mock_svc = MagicMock()
        mock_svc.get_kv_secret.return_value = "shim-secret"
        with patch("api.services.azure_auth.get_auth_service", return_value=mock_svc):
            result = azure_auth.get_kv_secret("my-secret")
        assert result == "shim-secret"
