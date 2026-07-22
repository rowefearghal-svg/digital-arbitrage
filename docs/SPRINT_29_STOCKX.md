# Sprint 29 – StockX Provider Integration

## Summary

This sprint adds a live marketplace provider for [StockX](https://stockx.com).
It authenticates with OAuth 2.0 authorization-code + PKCE, searches the StockX
public catalog, and maps each product to a canonical :class:`Listing` using the
``/v2/catalog/products/{id}/market-data`` endpoint for pricing.

The existing architecture is preserved:

* **Playwright is only used for authentication/token acquisition and refresh.**
* **All normal API calls use the existing :class:`HttpClient`.**

No scraping and no new external dependencies are required for the provider
itself; Playwright remains an optional dependency used only for the browser
authentication flow.

## What changed

### New provider: `StockXProvider`

* File: `src/digital_arbitrage/providers/live/stockx_provider.py`
* Endpoints:
  * `GET /v2/catalog/search` – free-text product search (paginated).
  * `GET /v2/catalog/products/{id}/market-data?currencyCode=USD` – per-variant
    market pricing used to derive a product-level lowest ask.
* Auth: OAuth 2.0 authorization-code + PKCE via the user's cached refresh
  token; falls back to Playwright when the standard HTTP token refresh is
  Cloudflare-blocked.
* Required environment variables:
  * `STOCKX_API_KEY` – ``x-api-key`` header.
  * `STOCKX_CLIENT_ID`
  * `STOCKX_CLIENT_SECRET`
* Config class: `StockXConfig` extends `LiveProviderConfig` with
  `currency_code`, `oauth_authorization_url`, `oauth_token_url`, `oauth_scope`,
  and `oauth_audience`.
* Canonical mapping:
  * `listing_id` -> StockX `productId`
  * `title` -> StockX `title`
  * `url` -> `https://stockx.com/{urlKey}`
  * `price` -> minimum `lowestAskAmount` across variants (or `None`)
  * `currency` -> configured `currency_code`
  * `condition` -> `Condition.NEW`
  * `extra` -> style id, brand, colorway, gender, release date, retail price,
    variant count, lowest ask, and highest bid.

### Auth fixes

* `auth_code.py`
  * Fixed missing `self._refresh_leeway` assignment in
    `OAuthAuthorizationCodeAuthProvider.__init__`.
  * `TokenCache.save` now merges new tokens with the existing cache, so a
    refresh response that omits a new refresh token cannot accidentally wipe
    the stored one.
* `auth_browser.py`
  * Added optional Playwright storage-state persistence. After a successful
    browser flow the cookie/local-storage state is saved to
    ``~/.digital_arbitrage/stockx_playwright_state.json`` and reused on the
    next run, which greatly reduces repeated Cloudflare challenges.

### CLI integration

* `src/digital_arbitrage/pipeline/cli.py`
  * `arb auth stockx` runs the one-time browser OAuth flow and caches the
    refresh token.
  * `--provider stockx` is documented and supported in `arb scan`.

### Tests

* `tests/test_stockx_provider.py` – hermetic tests for config, request
  construction, search/market-data mapping, pagination, market-data failure
  handling, and env-based builder wiring.
* `tests/fixtures/stockx/` – committed, sanitized JSON fixtures.
* `tests/test_live_auth.py` – regression tests for the `TokenCache` merge
  behaviour and the `OAuthAuthorizationCodeAuthProvider` refresh-leeway fix.

## Authentication flow

1. Ensure `STOCKX_API_KEY`, `STOCKX_CLIENT_ID`, and `STOCKX_CLIENT_SECRET` are
   set in the environment (e.g. `.env`).
2. Run the browser flow once:
   ```bash
   arb auth stockx
   ```
   This opens a browser and completes OAuth authorization-code + PKCE inside the
   browser context. The redirect is intercepted by Playwright, so no local HTTPS
   callback server or SSL certificate is required. The refresh token is cached
   at ``~/.digital_arbitrage/stockx_tokens.json``.
3. Normal scans now use the cached refresh token:
   ```bash
   arb scan "nike dunk low" --provider stockx --limit 5
   ```

If the standard HTTP token refresh is blocked by Cloudflare, the auth provider
falls back to a Playwright browser exchange. Because the browser storage state
is persisted, this fallback should only require solving a CAPTCHA once.

## Verification

Live endpoint verification (performed during development):

* OAuth token refresh via browser fallback: success.
* `GET /v2/catalog/search`: HTTP 200.
* `GET /v2/catalog/products/{productId}/market-data`: HTTP 200, returning
  per-variant market data.

All tests pass:

```bash
python -m pytest tests/ -q
```

## Future work / notes

* The provider currently emits one `Listing` per product, using the minimum
  lowest ask across all variants. If size-level granularity becomes important we
  can extend the mapping to emit one listing per variant in a follow-up sprint.
* The StockX API can return `null` for `lowestAskAmount` when no asks are
  present; the provider keeps the listing but leaves `price` as `None` so the
  opportunity scorer can treat it as an unpriced market.
