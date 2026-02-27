"""Tests for DigiKeyClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vendor_api_tool.digikey import DigiKeyClient
from vendor_api_tool.models import ComponentResult


@pytest.fixture()
def client() -> DigiKeyClient:
    return DigiKeyClient(client_id="test-id", client_secret="test-secret")


def test_authenticate_success(client: DigiKeyClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "tok-abc"}

    with patch.object(client._http, "post", return_value=mock_resp):
        result = client.authenticate()

    assert result is True
    assert client._token == "tok-abc"
    assert client._available is True


def test_authenticate_failure(client: DigiKeyClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"

    with patch.object(client._http, "post", return_value=mock_resp):
        result = client.authenticate()

    assert result is False
    assert client._available is False
    assert client._token is None


def test_search_mpn_success(client: DigiKeyClient) -> None:
    client._token = "existing-token"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "Product": {
            "ManufacturerPartNumber": "LM358DR",
            "Manufacturer": {"Name": "Texas Instruments"},
            "ProductDescription": "IC OPAMP GP 2 CIRCUIT 8SOIC",
            "PrimaryDatasheet": "https://example.com/lm358.pdf",
            "ProductUrl": "https://digikey.com/product/LM358DR",
        }
    }

    with patch.object(client._http, "get", return_value=mock_resp):
        result = client.search_mpn("LM358DR")

    assert isinstance(result, ComponentResult)
    assert result.source == "digikey"
    assert result.mpn == "LM358DR"
    assert result.manufacturer == "Texas Instruments"
    assert result.description == "IC OPAMP GP 2 CIRCUIT 8SOIC"
    assert result.datasheet_url == "https://example.com/lm358.pdf"
    assert result.product_url == "https://digikey.com/product/LM358DR"


def test_search_mpn_unavailable(client: DigiKeyClient) -> None:
    client._available = False

    with patch.object(client._http, "get") as mock_get:
        result = client.search_mpn("LM358DR")

    assert result is None
    mock_get.assert_not_called()


def test_search_mpn_auto_authenticates(client: DigiKeyClient) -> None:
    assert client._token is None

    auth_resp = MagicMock()
    auth_resp.status_code = 200
    auth_resp.json.return_value = {"access_token": "auto-token"}

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "Product": {
            "ManufacturerPartNumber": "ATmega328P",
            "Manufacturer": {"Name": "Microchip"},
            "ProductDescription": "8-bit MCU",
            "PrimaryDatasheet": "",
            "ProductUrl": "",
        }
    }

    with patch.object(client._http, "post", return_value=auth_resp):
        with patch.object(client._http, "get", return_value=search_resp):
            result = client.search_mpn("ATmega328P")

    assert result is not None
    assert client._token == "auto-token"
    assert result.mpn == "ATmega328P"
