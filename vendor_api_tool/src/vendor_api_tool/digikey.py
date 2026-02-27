"""DigiKey v4 REST API client (secondary/stub)."""

from __future__ import annotations

import logging

import httpx

from vendor_api_tool.models import ComponentResult

_log = logging.getLogger(__name__)

_TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
_SEARCH_URL = "https://api.digikey.com/products/v4/search/{mpn}/productdetails"


class DigiKeyClient:
    """Client for DigiKey v4 product search API.

    This is a secondary data source. Authentication may fail if a business
    account is required — in that case, methods return None gracefully.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._http = httpx.Client(timeout=30.0)
        self._available = True  # Set to False if auth fails

    def authenticate(self) -> bool:
        """Attempt OAuth2 client credentials authentication. Returns True on success."""
        try:
            resp = self._http.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            if resp.status_code != 200:
                _log.warning("DigiKey auth failed: %s %s", resp.status_code, resp.text[:200])
                self._available = False
                return False
            self._token = resp.json()["access_token"]
            return True
        except Exception:
            _log.warning("DigiKey auth error", exc_info=True)
            self._available = False
            return False

    def search_mpn(self, mpn: str) -> ComponentResult | None:
        """Search for a component by MPN. Returns None if unavailable or on error."""
        if not self._available:
            return None

        if self._token is None:
            if not self.authenticate():
                return None

        try:
            resp = self._http.get(
                _SEARCH_URL.format(mpn=mpn),
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "X-DIGIKEY-Client-Id": self._client_id,
                },
            )
            if resp.status_code != 200:
                _log.warning("DigiKey search failed for %s: %s", mpn, resp.status_code)
                return None

            data = resp.json()
            product = data.get("Product", {})
            if not product:
                return None

            return ComponentResult(
                source="digikey",
                mpn=product.get("ManufacturerPartNumber", mpn),
                manufacturer=product.get("Manufacturer", {}).get("Name", ""),
                description=product.get("ProductDescription", ""),
                datasheet_url=product.get("PrimaryDatasheet", ""),
                product_url=product.get("ProductUrl", ""),
            )
        except Exception:
            _log.warning("DigiKey search error for %s", mpn, exc_info=True)
            return None

    def close(self) -> None:
        self._http.close()
