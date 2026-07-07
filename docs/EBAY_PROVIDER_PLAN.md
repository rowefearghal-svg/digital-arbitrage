# eBay Browse API — First Real Provider: Research & Integration Plan

**Status:** Research / design only. **No provider code is implemented in this
sprint** (Sprint 22). This document plans how the first real, read-only
marketplace provider (eBay Browse API) will map onto the existing live-provider
framework (`digital_arbitrage.providers.live`, ADR-015), and what — if anything —
must change before implementation.

> Scope guardrails carried over from prior sprints: **read-only**, **no
> scraping**, **standard library only**, **no secrets in the repo or CI**, and
> **backwards compatible** with the existing mock providers.

---

## 1. Why the Browse API

The eBay **Browse API** (`buy/browse/v1`) is the correct surface for our use
case:

- It is a **search** API — `GET /item_summary/search?q=...` returns item
  summaries (title, price, condition, location, image, URL) that map almost
  1:1 onto our `Listing` model.
- It authenticates with an **application** OAuth token (client-credentials
  grant), i.e. **no end-user login / consent flow** — exactly right for a
  server-side, read-only scanner.
- It is officially supported and documented, so we avoid scraping entirely.

It is *not* the Finding API (deprecated/legacy) nor the Marketplace Insights API
(sold/completed data; requires a separate, harder-to-obtain license).

---

## 2. Account & access requirements

| Requirement | Detail |
| --- | --- |
| eBay Developer account | Free; join the eBay Developers Program. |
| Application keyset | Production + Sandbox keysets, each with a **Client ID (App ID)** and **Client Secret (Cert ID)**. |
| Buy API license | The Buy APIs "require an additional license." Basic Browse access is available with the standard keyset for testing; **production/higher volume requires accepting the API License Agreement and passing the free Application Growth Check**. |
| eBay Partner Network (EPN) | *Optional.* Only needed if we want the affiliate URL (`itemAffiliateWebUrl`) for commissions. Not required for our price-comparison use case — we use the plain `itemWebUrl`. |
| Marketplace access | Choose a marketplace (e.g. `EBAY_IE`, `EBAY_GB`, `EBAY_US`); see §7. |

**Sandbox** exists and mirrors production by swapping the host
(`api.ebay.com` → `api.sandbox.ebay.com`); sandbox has limited/mock inventory,
so it is useful for auth wiring but not for realistic data.

---

## 3. Authentication

**Grant flow:** OAuth 2.0 **client credentials** → an *Application access token*.
No user token, no refresh token, no redirect/RuName.

**Mint a token** (once, then cache until expiry):

```
POST https://api.ebay.com/identity/v1/oauth2/token
Authorization: Basic base64("<client_id>:<client_secret>")
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope
```

Response:

```json
{ "access_token": "v^1.1#i^1#...", "expires_in": 7200, "token_type": "Application Access Token" }
```

- **Scope:** `https://api.ebay.com/oauth/api_scope` (the base scope; sufficient
  for `item_summary/search`).
- **TTL:** ~7200s (2h). The token must be **cached and re-minted on expiry**.
- **Use:** every Browse call sends `Authorization: Bearer <access_token>`.

> **Framework implication (important):** our current `HttpClient` builds a static
> `Authorization: Bearer <config.api_key>` from config on every request. eBay
> needs a *minted, rotating* token, not a static key. This is the one genuine
> gap — see §9 (a small `AuthProvider` hook) and ADR-016.

---

## 4. Rate limits

| Limit | Value |
| --- | --- |
| Browse API (all methods except `getItems`) | **5,000 calls/day** (default) |
| `getItems` | 5,000 calls/day (separate bucket) |
| Higher limits | via the free Application Growth Check |
| OAuth token endpoint | Separate token-minting limits; mitigated by caching the 2h token |

**Design consequence:** 5,000/day ≈ one call every ~17s sustained. A per-second
`TokenBucketRateLimiter` (already in the framework) prevents bursts but does
**not** enforce a daily budget — a per-day counter is a separate concern (see
§9 / debt). Actual usage can be inspected at runtime via the Analytics API
`getRateLimits` (`api_name=browse`) if we ever want live budget awareness.

---

## 5. Search endpoint & request shape

**Endpoint:** `GET https://api.ebay.com/buy/browse/v1/item_summary/search`

**Required headers:**

- `Authorization: Bearer <token>`
- `X-EBAY-C-MARKETPLACE-ID: <marketplace>` (e.g. `EBAY_IE`)
- *(recommended)* `X-EBAY-C-ENDUSERCTX` when sorting by price (adds shipping to
  the total used for sort); optional for us initially.

**Query parameters we will use:**

| Param | Use |
| --- | --- |
| `q` | free-text keyword query (max 100 chars; wildcard `*` not allowed) |
| `limit` | page size, **1–200**, default 50 |
| `offset` | 0-based offset for pagination |
| `filter` | optional field filters, e.g. `price:[10..500]`, `conditions:{USED}`, `buyingOptions:{FIXED_PRICE}` |
| `sort` | optional, e.g. `price` (default is Best Match) |

Example:

```
GET /buy/browse/v1/item_summary/search?q=rtx%204090&limit=50&offset=0
X-EBAY-C-MARKETPLACE-ID: EBAY_IE
Authorization: Bearer v^1.1#...
```

---

## 6. Pagination model

Offset/limit paging with a server-provided `next` link:

- Response carries `total`, `limit`, `offset`, `href`, and (when more pages
  exist) `next` / `prev` absolute URLs.
- **Hard cap:** the search can return at most **10,000 items**, so `offset` must
  stay `< 10,000` (error `12029` otherwise).

**Maps cleanly onto our framework.** Our `paginate(fetch_page, max_results,
max_pages)` calls `fetch_page(page_number)` with a **1-based page number**; the
provider converts that to `offset = (page_number - 1) * page_size`. `Page.has_more`
is set from the presence of `next` (or `offset + limit < total`). `capabilities.
supports_pagination = True` and `capabilities.max_page_size = 200` drive the base
class's loop and page sizing automatically.

---

## 7. Response fields → `Listing` mapping

Response: `{ href, total, limit, offset, next, prev, itemSummaries: [ ... ] }`.

Each `itemSummaries[i]` maps to one `Listing`:

| `Listing` field | eBay source | Notes |
| --- | --- | --- |
| `listing_id` | `itemId` | RESTful item id (e.g. `v1|123...|0`). Stable, unique. |
| `title` | `title` | Required; non-empty (guaranteed by API). |
| `provider` | — | Constant `"ebay_browse"` (see §8). |
| `url` | `itemWebUrl` | Public listing URL. (`itemAffiliateWebUrl` only if EPN.) |
| `price` | `price.value` | String decimal → `float`. May be absent for pure-auction items. |
| `currency` | `price.currency` | ISO 4217 (e.g. `EUR`, `GBP`, `USD`). |
| `location` | `itemLocation.{city, stateOrProvince, postalCode, country}` | Compose a short string, e.g. `"Dublin, IE"`; `country` is ISO 3166. |
| `condition` | `condition` / `conditionId` | Map to our `Condition` enum (see below). |
| `posted_at` | — | **Not provided** by item summaries. Leave `None`. (`itemCreationDate` exists on the `item` detail resource, not the summary.) |
| `extra["image_url"]` | `image.imageUrl` | Primary image. Model has no image field; stash in `extra` (no schema change). |
| `extra["buying_options"]` | `buyingOptions` (join) | e.g. `"FIXED_PRICE"` / `"AUCTION"`. |
| `extra["seller"]` | `seller.username` | Optional context. |
| `extra["condition_id"]` | `conditionId` | Preserve raw id for auditing. |

**Condition mapping** (`conditionId` is the stable signal; `condition` text is a
fallback):

| eBay `conditionId` | eBay text (examples) | `Condition` |
| --- | --- | --- |
| `1000` | New | `NEW` |
| `1500`, `1750` | New other / open box | `NEW` |
| `2000`, `2010`, `2020`, `2030` | Certified / Excellent / Very Good / Good Refurbished | `REFURBISHED` |
| `2500` | Seller refurbished | `REFURBISHED` |
| `3000`, `4000`, `5000`, `6000` | Used / Very Good / Good / Acceptable | `USED` |
| `7000` | For parts or not working | `USED` |
| missing / unknown | — | `UNKNOWN` |

**Price/currency:** `price` is `{ value: "1234.56", currency: "EUR" }`. Parse
`value` with `require_number`-style validation (reject non-numeric); pass
`currency` straight through. Some auction-only listings omit `price` — allow
`price=None` (our model already permits it).

**Item URL:** `itemWebUrl` (always present). `itemHref` is the API self-link (not
user-facing); do not use it as `Listing.url`.

**Location:** compose from `itemLocation`. Only `country` is reliably present;
`city`/`postalCode` are often present for used/local items.

**Images:** `image.imageUrl` (primary) plus `thumbnailImages[]` /
`additionalImages[]`. Store the primary in `extra["image_url"]`.

---

## 8. Mapping onto the live-provider framework

The Browse API fits the framework with **no changes to the mock providers** and
**one small, additive framework extension** (auth — §9).

```python
class EbayBrowseProvider(LiveProvider):
    name = "ebay_browse"                      # NOT "ebay" — see below
    capabilities = ProviderCapabilities(
        supports_free_text_search=True,
        supports_pagination=True,
        supports_price_filter=True,
        supports_condition_filter=True,
        supports_sorting=True,
        requires_api_key=True,                # client_id/secret required
        max_page_size=200,
        max_results=10_000,                   # eBay's offset cap
        supported_currencies=("EUR", "GBP", "USD"),
    )

    def build_request(self, query, *, page, page_size) -> HttpRequest:
        offset = (page - 1) * page_size
        return HttpRequest(
            method="GET",
            url=resolve_url(self.config.base_url, "/buy/browse/v1/item_summary/search"),
            params={"q": query[:100], "limit": str(page_size), "offset": str(offset)},
            headers={"X-EBAY-C-MARKETPLACE-ID": self.config.extra_headers.get(...)},
        )

    def parse_response(self, response, *, query) -> Page[Listing]:
        payload = ensure_mapping(parse_json(response, provider=self.name))
        summaries = ensure_list(payload.get("itemSummaries") or [], ...)
        listings = tuple(self._to_listing(ensure_mapping(s, ...)) for s in summaries)
        has_more = "next" in payload  # or offset + limit < total
        return Page(items=listings, has_more=has_more)
```

What the framework already gives us for free:

- **HTTP + retries + backoff + rate limiting + structured logging** via
  `HttpClient` / `RetryPolicy` / `TokenBucketRateLimiter`.
- **Typed errors**: eBay `429` → `ProviderRateLimitError` (honours
  `Retry-After`), `5xx` → retryable `ProviderHTTPError`, `4xx` (e.g. `400`
  invalid `q`) → non-retryable `ProviderHTTPError`, malformed JSON → `Provider
  ResponseError`. eBay error bodies (`{ "errors": [{ "errorId": 12001, ... }] }`)
  can be surfaced in the exception message.
- **Pagination** via `paginate` + capability flags (§6).
- **Validation** helpers turn the untrusted JSON into typed values (§7).
- **`Provider` compatibility**: `EbayBrowseProvider` *is a* `Provider`, so it
  works with the scanner once wiring is added (§10).

### Provider name: `ebay_browse`, not `ebay`

The existing **mock** provider is registered as `"ebay"`. Registering a live
provider under the same name would collide in `PROVIDER_REGISTRY`
(`register_provider` raises on duplicates). Use **`ebay_browse`** — it is
distinct, self-describing (which eBay API), and lets the mock and live providers
coexist during rollout.

---

## 9. Recommended config, secrets & required framework additions

### 9.1 Config structure

Reuse `LiveProviderConfig` (already validated, `from_dict` with nested `retry`)
plus a thin eBay-specific config for the fields it lacks (marketplace, OAuth
endpoint, credentials). Proposed TOML, loaded into a `[providers.ebay_browse]`
table:

```toml
[providers.ebay_browse]
base_url = "https://api.ebay.com"
marketplace_id = "EBAY_IE"          # EBAY_IE | EBAY_GB | EBAY_US | ...
timeout = 10.0
page_size = 50                       # <= 200
max_results = 200                    # our cap; <= 10000
default_currency = "EUR"
rate_limit_per_second = 3.0
rate_limit_burst = 5
# credentials come from SECRETS, never the file (see 9.2)

[providers.ebay_browse.retry]
max_attempts = 3
backoff_base = 0.5
backoff_factor = 2.0
retry_on_status = [429, 500, 502, 503, 504]
```

Two small config additions beyond today's `LiveProviderConfig`:

- `marketplace_id: str` — sent as `X-EBAY-C-MARKETPLACE-ID`.
- `oauth_token_url: str` — default `https://api.ebay.com/identity/v1/oauth2/token`
  (sandbox variant swaps the host).

These can live either as new `LiveProviderConfig` fields or on a subclass
`EbayBrowseConfig(LiveProviderConfig)`. Prefer the **subclass** to keep the
generic config lean (the base config stays marketplace-agnostic).

### 9.2 Required secrets

Never in the repo or CI. Two secrets:

| Secret name | Purpose |
| --- | --- |
| `EBAY_CLIENT_ID` | OAuth client id (App ID) |
| `EBAY_CLIENT_SECRET` | OAuth client secret (Cert ID) |

Loaded from the environment at runtime and passed into the provider/auth
provider. `capabilities.requires_api_key=True` makes construction fail fast if
they are absent.

### 9.3 Required framework addition — token auth

The single real gap. eBay needs a **minted, cached, auto-refreshed** bearer
token, whereas `HttpClient` currently injects a static `config.api_key`. Options,
cheapest first:

1. **`AuthProvider` seam (recommended).** Add a tiny pluggable interface the
   `HttpClient` consults for the `Authorization` header per request:

   ```python
   class AuthProvider(Protocol):
       def authorization(self) -> str | None: ...   # e.g. "Bearer <token>"
   ```

   Provide an `OAuthClientCredentialsAuth(token_url, client_id, client_secret,
   http_client)` that mints via the token endpoint, caches the token, and
   re-mints ~60s before `expires_in`. This keeps the client generic and testable
   (inject a fake transport for the token endpoint too). *Small, additive; no
   change to existing providers.*

2. **Provider-managed header.** The provider mints the token itself and passes it
   via per-request `headers`. Simpler but leaks auth concerns into the provider
   and duplicates caching logic per provider. Acceptable as a first cut.

The plan recommends **option 1** as a ~1-file framework extension in the
*implementation* sprint (not now).

### 9.4 Optional (deferred) — daily budget guard

A per-day call counter to respect the 5,000/day quota (the per-second limiter
does not). Out of scope for the first cut; documented as debt.

---

## 10. Tests, fixtures & CI policy

**CI uses the mocked transport ONLY — no network, no secrets, deterministic.**
This follows the framework's existing pattern: inject a fake `Transport` into
`HttpClient` so no real HTTP occurs.

- **Fixtures.** Capture a handful of **real** Browse responses once, **sanitise**
  them (drop tokens/PII, trim `itemSummaries` to a few entries), and commit them
  under `tests/fixtures/ebay/` (e.g. `search_page1.json`, `search_page2.json`,
  `empty.json`, `error_12001.json`, `rate_limited.json`).
- **`FixtureTransport`.** A `Transport` that returns the fixture matching the
  request (by `offset`/path), used to drive `parse_response`, pagination, and
  error mapping deterministically.
- **Unit tests to add:** field mapping (all `Listing` fields incl. condition-id
  table and price/currency/`None`-price), pagination across two pages + `total`
  cap, empty results, malformed JSON → `ProviderResponseError`, eBay error body
  → `ProviderHTTPError`, `429` → `ProviderRateLimitError`, marketplace header
  present, `q` truncation to 100 chars, and the OAuth auth provider (token mint +
  cache + refresh, all via a fake transport).
- **Live smoke test (opt-in, NOT in CI).** A single test guarded by the presence
  of `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` env vars (`pytest.mark.skipif`), run
  manually to validate real wiring. CI never sets these, so it is always skipped
  there.

---

## 11. Schema / model changes

**None required.** `Listing` already carries `listing_id`, `title`, `provider`,
`url`, `price`, `currency`, `location`, `condition`, `posted_at`, and an `extra:
dict[str, str]` catch-all. Image URL, buying options, seller, and raw
`conditionId` go into `extra`, so **no migration and no changes to existing
modules/persistence**. (A first-class `image_url` field could be considered later
but is explicitly out of scope to preserve backwards compatibility.)

The one **wiring** change for a *later* sprint (not a schema change): the
registry factory `create_provider(name)` calls `cls()` with no arguments, but a
`LiveProvider` needs a `LiveProviderConfig`. Enabling `arb scan` to select the
live provider will require a config-aware factory (e.g.
`create_provider(name, config)` or a registry of builders). Flagged here; handled
when we wire the provider into the pipeline.

---

## 12. API restrictions & terms that matter

- **Buy API license / Growth Check** required for production volume (§2).
- **Read-only** use here; we do not place orders or expose affiliate links.
- **Affiliate URLs:** commissions require EPN and using `itemAffiliateWebUrl`;
  we intentionally use the plain `itemWebUrl` (no EPN dependency).
- **10,000-item ceiling** per search; `offset < 10,000` (§6).
- **`q` ≤ 100 chars**, no `*` wildcard (§5) — truncate/validate in
  `build_request`.
- **Marketplace-specific** results and category ids; pick the marketplace via
  header (§7).
- **Data handling:** cache responsibly, respect the eBay API License Agreement,
  and never commit tokens or raw personal data (fixtures are sanitised).

---

## 13. Summary of recommendations

| Question | Recommendation |
| --- | --- |
| Provider name | **`ebay_browse`** (avoid colliding with the mock `ebay`). |
| Config | `EbayBrowseConfig(LiveProviderConfig)` adding `marketplace_id` + `oauth_token_url`; TOML `[providers.ebay_browse]`. |
| Secrets | `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` (env/secret store; never in repo/CI). |
| Auth | Add a small **`AuthProvider`** seam + `OAuthClientCredentialsAuth` (mint/cache/refresh). Only real framework change needed. |
| Tests/fixtures | Sanitised recorded JSON + a `FixtureTransport`; comprehensive mapping/pagination/error tests. |
| CI | **Mocked transport only**; live smoke test is opt-in via env-gated skip. |
| Schema | **No changes**; images/seller/etc. into `Listing.extra`. Registry factory needs a config-aware variant when wiring into the CLI (later). |
| Marketplace | Default `EBAY_IE` (EUR), configurable. |

**Next sprint (implementation):** add the `AuthProvider` seam, implement
`EbayBrowseProvider` + `EbayBrowseConfig`, commit sanitised fixtures + tests
(mocked transport), and wire an env-gated live smoke test — all read-only, stdlib
only, mocks untouched.
