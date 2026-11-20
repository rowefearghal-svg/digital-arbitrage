"""Bounded live-capability verification for the market-data layer.

Probes eBay Browse (search enrichment + getItem incl. COMPACT) and StockX
(catalog search, market-data, variants) using the existing provider
HttpClients and real credentials from the environment. Writes a sanitised
JSON report to var/market_data/verify/ (gitignored).

Budget: ~13 live requests total. Run from the repo root:

    python scripts/verify_live_capabilities.py
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

from digital_arbitrage.providers.live.ebay_browse import (
    EbayBrowseConfig,
    build_ebay_browse_provider_from_env,
)
from digital_arbitrage.providers.live.stockx_provider import (
    StockXConfig,
    build_stockx_provider_from_env,
)

OUT_DIR = Path("var/market_data/verify")


def _pseudonym(value: str) -> str:
    return "u_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _call(client_get, path: str, params: dict[str, str], stats: list[dict[str, Any]], label: str):
    started = time.monotonic()
    entry: dict[str, Any] = {"label": label, "path": path, "params": dict(params)}
    try:
        resp = client_get(path, params=params)
        entry["status"] = resp.status
        entry["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        stats.append(entry)
        return resp.json()
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        entry["error"] = type(exc).__name__
        entry["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        stats.append(entry)
        return None


def _sanitise_ebay_item(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    seller = out.get("seller")
    if isinstance(seller, dict):
        seller = dict(seller)
        if isinstance(seller.get("username"), str):
            seller["username"] = _pseudonym(seller["username"])
        out["seller"] = seller
    out.pop("itemAffiliateWebUrl", None)
    return out


def _ebay_item_field_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-field presence rate across itemSummaries."""
    counts: dict[str, int] = {}
    for item in items:
        for key in item:
            counts[key] = counts.get(key, 0) + 1
    n = len(items) or 1
    return {
        "items_examined": len(items),
        "field_presence": {
            k: {"count": v, "rate": round(v / n, 3)} for k, v in sorted(counts.items())
        },
    }


def verify_ebay() -> dict[str, Any]:
    report: dict[str, Any] = {"requests": []}
    config = EbayBrowseConfig.from_dict(
        {"base_url": "https://api.ebay.com", "marketplace_id": "EBAY_IE", "max_results": 5}
    )
    provider = build_ebay_browse_provider_from_env(config)
    stats = report["requests"]

    # 1. Plain search (as the current provider issues it).
    plain = _call(
        provider.http.get,
        "/buy/browse/v1/item_summary/search",
        {"q": "RTX 4090", "limit": "5", "offset": "0"},
        stats,
        "ebay_search_plain",
    )
    plain_items = (plain or {}).get("itemSummaries") or []
    report["search_plain"] = {
        "total": (plain or {}).get("total"),
        "items_returned": len(plain_items),
        "field_report": _ebay_item_field_report(plain_items),
    }

    # 2. Enriched search: EXTENDED fieldgroups + auction-inclusive filter.
    enriched = _call(
        provider.http.get,
        "/buy/browse/v1/item_summary/search",
        {
            "q": "RTX 4090",
            "limit": "5",
            "offset": "0",
            "fieldgroups": "EXTENDED",
            "filter": "buyingOptions:{AUCTION|FIXED_PRICE}",
        },
        stats,
        "ebay_search_enriched",
    )
    enr_items = (enriched or {}).get("itemSummaries") or []
    report["search_enriched"] = {
        "total": (enriched or {}).get("total"),
        "items_returned": len(enr_items),
        "field_report": _ebay_item_field_report(enr_items),
        "buying_options_seen": sorted(
            {opt for it in enr_items for opt in (it.get("buyingOptions") or [])}
        ),
        "sample_sanitised": _sanitise_ebay_item(enr_items[0]) if enr_items else None,
    }

    # 3. getItem full detail on the first item.
    item_id = None
    for it in enr_items or plain_items:
        if isinstance(it.get("itemId"), str):
            item_id = it["itemId"]
            break
    if item_id:
        enc = urllib.parse.quote(item_id, safe="")
        full = _call(
            provider.http.get,
            f"/buy/browse/v1/item/{enc}",
            {},
            stats,
            "ebay_getitem_full",
        )
        compact = _call(
            provider.http.get,
            f"/buy/browse/v1/item/{enc}",
            {"fieldgroups": "COMPACT"},
            stats,
            "ebay_getitem_compact",
        )
        avail = (full or {}).get("estimatedAvailabilities") or []
        report["getitem_full"] = {
            "returned": full is not None,
            "top_level_fields": sorted(full.keys()) if isinstance(full, dict) else [],
            "estimatedAvailabilities": avail,
            "has_description": bool((full or {}).get("description")),
            "localized_aspects_count": len((full or {}).get("localizedAspects") or []),
            "seller_keys": sorted(((full or {}).get("seller") or {}).keys()),
        }
        report["getitem_compact"] = {
            "returned": compact is not None,
            "top_level_fields": sorted(compact.keys()) if isinstance(compact, dict) else [],
        }
    else:
        report["getitem_full"] = {"returned": False, "note": "no itemId in search results"}
    return report


def verify_stockx() -> dict[str, Any]:
    report: dict[str, Any] = {"requests": []}
    config = StockXConfig.from_dict({"base_url": "https://api.stockx.com", "max_results": 3})
    provider = build_stockx_provider_from_env(config)
    stats = report["requests"]

    # 1. GPU-family query (expected low/zero coverage - recorded, not an error).
    gpu = _call(
        provider.http.get,
        "/v2/catalog/search",
        {"query": "RTX 4090", "pageNumber": "1", "pageSize": "3"},
        stats,
        "stockx_search_gpu",
    )
    report["search_gpu"] = {
        "count": (gpu or {}).get("count"),
        "products_returned": len((gpu or {}).get("products") or []),
    }

    # 2. Catalogue-heavy query to exercise data shapes.
    search = _call(
        provider.http.get,
        "/v2/catalog/search",
        {"query": "nike dunk low", "pageNumber": "1", "pageSize": "2"},
        stats,
        "stockx_search_sneaker",
    )
    products = (search or {}).get("products") or []
    report["search_sneaker"] = {
        "count": (search or {}).get("count"),
        "products_returned": len(products),
        "product_fields": sorted(products[0].keys()) if products else [],
    }

    if not products:
        return report
    product_id = products[0].get("productId")
    if not product_id:
        return report

    # 3. Product-level market data (the call the provider already makes).
    md = _call(
        provider.http.get,
        f"/v2/catalog/products/{product_id}/market-data",
        {"currencyCode": "USD"},
        stats,
        "stockx_market_data",
    )
    md_list = md if isinstance(md, list) else []
    report["market_data"] = {
        "variants_returned": len(md_list),
        "variant_fields": sorted(md_list[0].keys()) if md_list else [],
        "fields_currently_discarded": (
            sorted(set(md_list[0].keys()) - {"lowestAskAmount", "highestBidAmount"})
            if md_list
            else []
        ),
        "sample_sanitised": md_list[0] if md_list else None,
    }

    # 4. Variants endpoint (new call - variant identity).
    variants = _call(
        provider.http.get,
        f"/v2/catalog/products/{product_id}/variants",
        {},
        stats,
        "stockx_variants",
    )
    var_list = variants if isinstance(variants, list) else []
    report["variants"] = {
        "variants_returned": len(var_list),
        "variant_fields": sorted(var_list[0].keys()) if var_list else [],
        "sample_sanitised": var_list[0] if var_list else None,
    }
    return report


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"ebay": None, "stockx": None, "errors": []}
    try:
        result["ebay"] = verify_ebay()
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"ebay: {type(exc).__name__}: {exc}")
    try:
        result["stockx"] = verify_stockx()
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"stockx: {type(exc).__name__}: {exc}")

    out_path = OUT_DIR / "live_capability_report.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_path}")
    for side in ("ebay", "stockx"):
        data = result.get(side) or {}
        for req in data.get("requests", []):
            print(
                f"  {req['label']}: status={req.get('status')} "
                f"err={req.get('error')} {req['elapsed_ms']}ms"
            )
    for err in result["errors"]:
        print(f"  ERROR {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
