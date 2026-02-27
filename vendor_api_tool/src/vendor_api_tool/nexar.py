"""Nexar/Octopart GraphQL client for component lookup."""

from __future__ import annotations

import httpx

from vendor_api_tool.models import ComponentResult


_TOKEN_URL = "https://identity.nexar.com/connect/token"
_GRAPHQL_URL = "https://api.nexar.com/graphql/"

_SEARCH_MPN_QUERY = """
query SearchMpn($mpn: String!, $limit: Int!) {
  supSearchMpn(q: $mpn, limit: $limit) {
    results {
      part {
        mpn
        manufacturer {
          name
        }
        shortDescription
        bestDatasheet {
          url
        }
        specs {
          attribute {
            name
          }
          displayValue
        }
        bestImage {
          url
        }
        sellers {
          company {
            name
          }
          offers {
            inventoryLevel
            prices {
              price
              currency
              quantity
            }
          }
        }
      }
    }
  }
}
"""


class NexarError(Exception):
    """Raised on Nexar API errors."""


class NexarClient:
    """Client for the Nexar/Octopart supply chain API."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._http = httpx.Client(timeout=30.0)

    def authenticate(self) -> None:
        """Obtain an OAuth2 bearer token using client credentials."""
        resp = self._http.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if resp.status_code != 200:
            raise NexarError(f"Authentication failed: {resp.status_code} {resp.text}")
        self._token = resp.json()["access_token"]

    def search_mpn(self, mpn: str, limit: int = 3) -> list[ComponentResult]:
        """Search for components by MPN. Returns list of results."""
        if self._token is None:
            self.authenticate()

        resp = self._http.post(
            _GRAPHQL_URL,
            json={"query": _SEARCH_MPN_QUERY, "variables": {"mpn": mpn, "limit": limit}},
            headers={"Authorization": f"Bearer {self._token}"},
        )

        if resp.status_code == 401:
            # Token expired, re-authenticate and retry once
            self.authenticate()
            resp = self._http.post(
                _GRAPHQL_URL,
                json={"query": _SEARCH_MPN_QUERY, "variables": {"mpn": mpn, "limit": limit}},
                headers={"Authorization": f"Bearer {self._token}"},
            )

        if resp.status_code != 200:
            raise NexarError(f"GraphQL request failed: {resp.status_code} {resp.text}")

        data = resp.json()
        if "errors" in data:
            raise NexarError(f"GraphQL errors: {data['errors']}")

        return self._parse_results(mpn, data)

    def _parse_results(self, mpn: str, data: dict) -> list[ComponentResult]:
        results: list[ComponentResult] = []
        search_results = data.get("data", {}).get("supSearchMpn", {}).get("results", [])

        for result in search_results:
            part = result.get("part", {})
            if not part:
                continue

            # Extract weight from specs if available
            weight = self._extract_weight(part.get("specs", []))

            # Collect all specs as raw_specs
            raw_specs: dict[str, str] = {}
            for spec in part.get("specs", []):
                attr_name = spec.get("attribute", {}).get("name", "")
                if attr_name:
                    raw_specs[attr_name] = spec.get("displayValue", "")

            datasheet = part.get("bestDatasheet") or {}

            results.append(
                ComponentResult(
                    source="nexar",
                    mpn=part.get("mpn", mpn),
                    manufacturer=(part.get("manufacturer") or {}).get("name", ""),
                    description=part.get("shortDescription", ""),
                    weight_grams=weight,
                    datasheet_url=datasheet.get("url", ""),
                    product_url="",
                    raw_specs=raw_specs,
                )
            )

        return results

    @staticmethod
    def _extract_weight(specs: list[dict]) -> float | None:
        """Try to find weight in the specs array."""
        weight_keys = {"weight", "mass", "net weight", "unit weight"}
        for spec in specs:
            attr_name = (spec.get("attribute", {}).get("name", "")).lower()
            if attr_name in weight_keys:
                return _parse_weight_string(spec.get("displayValue", ""))
        return None

    def close(self) -> None:
        self._http.close()


def _parse_weight_string(value: str) -> float | None:
    """Parse a weight string like '1.5 g' or '15 mg' into grams."""
    import re

    value = value.strip().lower().replace(",", ".")
    match = re.match(r"([\d.]+)\s*(mg|g|kg|oz|lb|lbs)", value)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    conversions = {
        "mg": 0.001,
        "g": 1.0,
        "kg": 1000.0,
        "oz": 28.3495,
        "lb": 453.592,
        "lbs": 453.592,
    }
    return round(amount * conversions[unit], 4)
