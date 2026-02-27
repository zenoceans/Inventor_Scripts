# Plan: Vendor API & Datasheet PDF Scraping Spike

## Context

We need to validate which vendor APIs work for MPN-based component data lookup (description, weight, datasheet URL, product URL) and whether weight can be extracted from datasheet PDFs. This feeds into Goal 2 (Component Import from Vendors) of the strategy brief at `docs/strategy-brief.md`. The key finding from research is that **weight is not reliably available from any API** — PDF scraping is the most promising path.

## Project Setup

Create a new repo (separate from this notes repo):

```bash
mkdir vendor-api-spike && cd vendor-api-spike
uv init --python 3.13
uv add httpx python-dotenv pymupdf tabulate
uv add --dev ruff
```

### Structure

```
vendor-api-spike/
  pyproject.toml
  .env                    # API credentials (gitignored)
  .env.example            # Template: NEXAR_CLIENT_ID, NEXAR_CLIENT_SECRET, DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET
  .gitignore              # .env, *.pdf, __pycache__/, .venv/
  src/vendor_api_spike/
    __init__.py
    config.py             # Load .env, export credentials and URLs
    models.py             # ComponentResult dataclass
    nexar.py              # Nexar/Octopart GraphQL client
    digikey.py            # DigiKey v4 REST client
    datasheet.py          # PDF download + weight regex extraction
    main.py               # CLI: run all tests, print comparison table
```

## Manual Prerequisites (before coding)

1. **Nexar**: Sign up at https://nexar.com/api → get `client_id` and `client_secret`
2. **DigiKey**: Sign up at https://developer.digikey.com → create org → create Production App → enable "Product Information V4" → get `Client ID` and `Client Secret`, set redirect URI to `https://localhost:8080/callback`

## Implementation Steps

### Step 1: Shared model (`models.py`)

`ComponentResult` dataclass with fields: `source`, `mpn`, `manufacturer`, `description`, `datasheet_url`, `product_url`, `weight_grams` (float, normalized to grams), `price_usd`, `currency`, `sellers` (list), `raw_specs` (dict for debugging).

### Step 2: Config (`config.py`)

Load `.env` with `python-dotenv`. Export credential constants and API URLs:
- `NEXAR_TOKEN_URL = "https://identity.nexar.com/connect/token"`
- `NEXAR_GRAPHQL_URL = "https://api.nexar.com/graphql/"`
- `DIGIKEY_BASE_URL = "https://api.digikey.com"`

### Step 3: Nexar client (`nexar.py`) — PRIMARY DATA SOURCE

**Auth**: OAuth2 client credentials → POST to token URL with `grant_type=client_credentials`, `client_id`, `client_secret`. Returns bearer token.

**Query**: GraphQL `supSearchMpn` query:
```graphql
query SearchMPN($q: String!) {
  supSearchMpn(q: $q, limit: 3) {
    results {
      part {
        mpn
        shortDescription
        manufacturer { name }
        bestDatasheet { url }
        specs { attribute { name } displayValue }
        sellers {
          company { name }
          offers { clickUrl prices { price currency quantity } inventoryLevel }
        }
      }
    }
  }
}
```

**Parsing**: Extract description, manufacturer, datasheet URL, first seller clickUrl as product_url. Search `specs` for weight/mass attributes (rarely present but worth checking). Collect seller names.

**Free tier warning**: 1,000 matched parts *lifetime*. Use `limit: 1` during development. Cache raw JSON responses to a file so parsing logic can be re-tested without API calls.

### Step 4: DigiKey client (`digikey.py`) — SECONDARY

**Auth**: Try 2-legged OAuth2 (client credentials) first. If it fails (needs business account with credit), document the error and skip — Nexar alone may be sufficient for the spike.

**Query**: `GET /products/v4/search/{mpn}/productdetails` with headers `Authorization: Bearer`, `X-DIGIKEY-Client-Id`.

**Parsing**: Extract `ManufacturerProductNumber`, `Description.DetailedDescription`, `DatasheetUrl`, `ProductUrl`. No weight field exists.

### Step 5: Datasheet PDF weight scraper (`datasheet.py`)

**Download**: `httpx.get(url, follow_redirects=True)` → save to `datasheets/` folder.

**Extract weight**: Open PDF with `pymupdf`, extract text from all pages, search with regex patterns:
- Primary: `(?:weight|mass|gewicht|net\s*weight|unit\s*weight)[:\s]*(\d+[.,]?\d*)\s*(mg|g|kg|oz|lb|lbs)` (case insensitive)
- Fallback: Search lines containing "weight"/"mass"/"gewicht" for any `number + unit` pattern

**Normalize**: Convert all units to grams using a lookup table (mg→0.001, g→1, kg→1000, oz→28.35, lb→453.59).

**Handle European decimals**: Replace `,` with `.` before parsing.

**Return `None` if not found** — this is expected for many parts. The production tool will prompt for manual entry.

### Step 6: CLI entry point (`main.py`)

**Test MPNs** (hardcoded defaults, overridable via CLI args):
- `3044168` — Phoenix Contact UT 2.5 terminal block
- `LM358DR` — TI op-amp
- `1-104257-0` — TE Connectivity connector
- `2200484` — Phoenix Contact DIN rail terminal ST 2.5
- `STM32F103C8T6` — STM32 MCU

**Flow per MPN**:
1. Query Nexar → parse result
2. Query DigiKey → parse result
3. Get datasheet URL from whichever API returned it
4. Download PDF → extract weight
5. Collect all results

**Output**: Print a formatted comparison table using `tabulate` showing per-MPN: description (Nexar vs DigiKey), manufacturer, datasheet URL (yes/no), product URL (yes/no), weight from API, weight from PDF, seller names.

**Run**: `uv run python -m vendor_api_spike.main`

## Implementation Order

| Order | File | Test by |
|-------|------|---------|
| 1 | `pyproject.toml`, `.env.example`, `.gitignore` | `uv sync` succeeds |
| 2 | `models.py` | Import succeeds |
| 3 | `config.py` | Print env vars |
| 4 | `nexar.py` | Standalone auth + one MPN query, print raw JSON |
| 5 | `digikey.py` | Standalone auth + one MPN query |
| 6 | `datasheet.py` | Download a known PDF URL, extract weight |
| 7 | `main.py` | Full run with all test MPNs |

## Verification

1. Nexar returns description + datasheet URL for all test MPNs
2. Nexar shows RS/DigiKey/Mouser as sellers for Phoenix Contact parts (validates aggregation)
3. DigiKey auth works (or document why it doesn't)
4. PDF downloads succeed (follow redirects, handle timeouts)
5. Weight extracted from at least Phoenix Contact datasheets (they typically include weight in specs table)
6. Cross-reference: manually look up one MPN on vendor website and compare against API data
7. Document hit rate for weight extraction across all test MPNs

## Key Risks

| Risk | Mitigation |
|------|------------|
| Nexar free tier exhausted during dev | Cache raw JSON responses, use `limit: 1`, test parsing offline |
| DigiKey 2-legged auth needs business account | Skip DigiKey for spike if needed, Nexar covers it |
| PDF weight extraction low hit rate | Expected — document the rate, production tool falls back to manual entry |
| Datasheet URLs behind auth/paywall | Use `follow_redirects=True`, log and skip failures |

## API Research Summary

### Direct Vendor APIs

| Vendor | API? | Free? | MPN Lookup | Description | Weight | Datasheet URL |
|---|---|---|---|---|---|---|
| **DigiKey** | Yes (v4) | Yes | Yes | Yes | No | Yes |
| **RS Components** | Partner-only | No | Yes (if credentialed) | Yes | Unconfirmed | Yes |
| **Phoenix Contact** | No public API | N/A | N/A | N/A | N/A | N/A |
| **Mouser** | Yes | Yes | Yes | Yes | No | Yes (inconsistent) |

### Aggregator APIs

| Service | Free Tier | Description | Weight | Datasheet | Coverage |
|---|---|---|---|---|---|
| **Nexar/Octopart** | 1,000 parts lifetime | Yes | Sometimes (in specs) | Yes | 70M+ parts |
| **OEMsecrets** | Approval-based | No | No | Yes | 40M+ parts |
| **TrustedParts** | Yes (free) | Yes | No | Yes | 25M+ parts |

### Recommendation

- **Primary**: Nexar API — one call covers DigiKey, RS, Mouser, Phoenix Contact
- **Secondary**: DigiKey v4 direct — compare data quality
- **Weight**: PDF datasheet scraping with pymupdf + regex, manual fallback in production GUI
- **RS Components**: No separate integration needed — Nexar aggregates RS data
- **Phoenix Contact**: No direct API, but indexed in Nexar/DigiKey. BMEcat bulk download available for local database seeding.
