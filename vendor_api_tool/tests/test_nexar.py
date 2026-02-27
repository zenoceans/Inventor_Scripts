"""Tests for the Nexar/Octopart GraphQL client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vendor_api_tool.nexar import NexarClient, NexarError, _parse_weight_string


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHOENIX_CONTACT_RESPONSE = {
    "data": {
        "supSearchMpn": {
            "results": [
                {
                    "part": {
                        "mpn": "3044168",
                        "manufacturer": {"name": "Phoenix Contact"},
                        "shortDescription": "Terminal block, 2-position, 5.08 mm pitch",
                        "bestDatasheet": {
                            "url": "https://www.phoenixcontact.com/datasheets/3044168.pdf"
                        },
                        "bestImage": {"url": "https://www.phoenixcontact.com/images/3044168.jpg"},
                        "specs": [
                            {
                                "attribute": {"name": "Weight"},
                                "displayValue": "3.5 g",
                            },
                            {
                                "attribute": {"name": "Pitch"},
                                "displayValue": "5.08 mm",
                            },
                            {
                                "attribute": {"name": "Number of Positions"},
                                "displayValue": "2",
                            },
                        ],
                        "sellers": [
                            {
                                "company": {"name": "Digi-Key"},
                                "offers": [
                                    {
                                        "inventoryLevel": 5000,
                                        "prices": [
                                            {"price": 0.55, "currency": "USD", "quantity": 1}
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                }
            ]
        }
    }
}

TOKEN_RESPONSE = {"access_token": "test-token-abc123", "token_type": "Bearer", "expires_in": 3600}


@pytest.fixture
def client():
    return NexarClient(client_id="test-id", client_secret="test-secret")


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    return mock


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


def test_authenticate_success(client):
    mock_resp = _make_mock_response(200, TOKEN_RESPONSE)

    with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
        client.authenticate()

    assert client._token == "test-token-abc123"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["grant_type"] == "client_credentials"
    assert kwargs["data"]["client_id"] == "test-id"
    assert kwargs["data"]["client_secret"] == "test-secret"


def test_authenticate_failure(client):
    mock_resp = _make_mock_response(401, {"error": "invalid_client"})

    with patch.object(client._http, "post", return_value=mock_resp):
        with pytest.raises(NexarError, match="Authentication failed: 401"):
            client.authenticate()

    assert client._token is None


# ---------------------------------------------------------------------------
# search_mpn tests
# ---------------------------------------------------------------------------


def test_search_mpn_success(client):
    token_resp = _make_mock_response(200, TOKEN_RESPONSE)
    graphql_resp = _make_mock_response(200, PHOENIX_CONTACT_RESPONSE)

    with patch.object(client._http, "post", side_effect=[token_resp, graphql_resp]):
        results = client.search_mpn("3044168")

    assert len(results) == 1
    r = results[0]
    assert r.source == "nexar"
    assert r.mpn == "3044168"
    assert r.manufacturer == "Phoenix Contact"
    assert r.description == "Terminal block, 2-position, 5.08 mm pitch"
    assert r.datasheet_url == "https://www.phoenixcontact.com/datasheets/3044168.pdf"
    assert r.product_url == ""
    assert r.weight_grams == pytest.approx(3.5)
    assert r.raw_specs["Weight"] == "3.5 g"
    assert r.raw_specs["Pitch"] == "5.08 mm"
    assert r.raw_specs["Number of Positions"] == "2"


def test_search_mpn_empty_results(client):
    client._token = "existing-token"
    empty_response = {"data": {"supSearchMpn": {"results": []}}}
    graphql_resp = _make_mock_response(200, empty_response)

    with patch.object(client._http, "post", return_value=graphql_resp):
        results = client.search_mpn("NONEXISTENT-PART")

    assert results == []


def test_search_mpn_auto_authenticates(client):
    assert client._token is None

    token_resp = _make_mock_response(200, TOKEN_RESPONSE)
    graphql_resp = _make_mock_response(200, {"data": {"supSearchMpn": {"results": []}}})

    with patch.object(client._http, "post", side_effect=[token_resp, graphql_resp]) as mock_post:
        client.search_mpn("ABC123")

    assert client._token == "test-token-abc123"
    assert mock_post.call_count == 2
    # First call goes to token URL
    first_call_args = mock_post.call_args_list[0]
    assert first_call_args[0][0] == "https://identity.nexar.com/connect/token"


def test_search_mpn_401_retries(client):
    client._token = "expired-token"

    unauthorized_resp = _make_mock_response(401, {"error": "token_expired"})
    token_resp = _make_mock_response(200, TOKEN_RESPONSE)
    graphql_success_resp = _make_mock_response(200, PHOENIX_CONTACT_RESPONSE)

    with patch.object(
        client._http,
        "post",
        side_effect=[unauthorized_resp, token_resp, graphql_success_resp],
    ) as mock_post:
        results = client.search_mpn("3044168")

    assert len(results) == 1
    assert results[0].mpn == "3044168"
    # Calls: 1st GraphQL (401) -> token refresh -> 2nd GraphQL (200)
    assert mock_post.call_count == 3
    assert client._token == "test-token-abc123"


def test_search_mpn_graphql_errors(client):
    client._token = "valid-token"
    error_response = {"errors": [{"message": "Field 'supSearchMpn' not found"}]}
    graphql_resp = _make_mock_response(200, error_response)

    with patch.object(client._http, "post", return_value=graphql_resp):
        with pytest.raises(NexarError, match="GraphQL errors"):
            client.search_mpn("ABC123")


def test_search_mpn_http_error(client):
    client._token = "valid-token"
    error_resp = _make_mock_response(500, {"message": "Internal Server Error"})

    with patch.object(client._http, "post", return_value=error_resp):
        with pytest.raises(NexarError, match="GraphQL request failed: 500"):
            client.search_mpn("ABC123")


# ---------------------------------------------------------------------------
# _parse_weight_string tests
# ---------------------------------------------------------------------------


def test_parse_weight_string_grams():
    assert _parse_weight_string("1.5 g") == pytest.approx(1.5)


def test_parse_weight_string_milligrams():
    assert _parse_weight_string("15 mg") == pytest.approx(0.015)


def test_parse_weight_string_kilograms():
    assert _parse_weight_string("0.8 kg") == pytest.approx(800.0)


def test_parse_weight_string_ounces():
    assert _parse_weight_string("2.1 oz") == pytest.approx(2.1 * 28.3495, rel=1e-4)


def test_parse_weight_string_pounds():
    assert _parse_weight_string("1 lb") == pytest.approx(453.592)


def test_parse_weight_string_pounds_plural():
    assert _parse_weight_string("0.5 lbs") == pytest.approx(453.592 * 0.5, rel=1e-4)


def test_parse_weight_string_no_space():
    assert _parse_weight_string("3.5g") == pytest.approx(3.5)


def test_parse_weight_string_uppercase():
    # The function lowercases the input, so "5 G" is treated as "5 g"
    assert _parse_weight_string("5 G") == pytest.approx(5.0)


def test_parse_weight_string_invalid():
    assert _parse_weight_string("heavy") is None


def test_parse_weight_string_empty():
    assert _parse_weight_string("") is None


def test_parse_weight_string_comma_decimal():
    assert _parse_weight_string("1,5 g") == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# _extract_weight tests
# ---------------------------------------------------------------------------


def test_extract_weight_from_specs_found():
    specs = [
        {"attribute": {"name": "Color"}, "displayValue": "Red"},
        {"attribute": {"name": "Weight"}, "displayValue": "3.5 g"},
        {"attribute": {"name": "Height"}, "displayValue": "10 mm"},
    ]
    result = NexarClient._extract_weight(specs)
    assert result == pytest.approx(3.5)


def test_extract_weight_from_specs_mass_key():
    specs = [{"attribute": {"name": "Mass"}, "displayValue": "500 mg"}]
    result = NexarClient._extract_weight(specs)
    assert result == pytest.approx(0.5)


def test_extract_weight_from_specs_net_weight():
    specs = [{"attribute": {"name": "Net Weight"}, "displayValue": "1.2 kg"}]
    result = NexarClient._extract_weight(specs)
    assert result == pytest.approx(1200.0)


def test_extract_weight_from_specs_not_found():
    specs = [
        {"attribute": {"name": "Color"}, "displayValue": "Blue"},
        {"attribute": {"name": "Pitch"}, "displayValue": "2.54 mm"},
    ]
    result = NexarClient._extract_weight(specs)
    assert result is None


def test_extract_weight_from_specs_empty():
    assert NexarClient._extract_weight([]) is None
