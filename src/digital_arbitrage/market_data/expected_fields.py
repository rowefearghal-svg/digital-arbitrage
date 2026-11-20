"""Per-provider field-expectation registry for the completeness report.

Every field is classified so a missing value is reported with a *reason*:

* ``required``   - must be present for the record to be usable; absence counts
  as a rejection, not a missing field.
* ``expected``   - normally returned; absence is a genuine data gap to report.
* ``optional``   - returned only for some records (e.g. ``epid``, ``itemEndDate``
  on Good-'Til-Cancelled listings); absence is informational.
* ``restricted`` - documented but gated (``watchCount`` needs an eBay App Check
  grant); absence is expected and reported as *restricted*, not missing.
* ``not_in_api`` - wanted for demand modelling but not exposed by the endpoint
  (sold prices, sale counts); reported as unavailable-through-source.
"""

from __future__ import annotations

EXPECTED_FIELDS: dict[str, dict[str, dict[str, str]]] = {
    "ebay_browse": {
        "search": {
            "itemId": "required",
            "title": "required",
            "price": "required",
            "itemWebUrl": "expected",
            "conditionId": "expected",
            "seller": "expected",
            "shippingOptions": "expected",
            "itemLocation": "expected",
            "itemCreationDate": "expected",
            "itemOriginDate": "expected",
            "buyingOptions": "expected",
            "categories": "expected",
            "image": "optional",
            "shortDescription": "optional",  # only with fieldgroups=EXTENDED
            "epid": "optional",
            "itemEndDate": "optional",  # absent on GTC listings
            "itemGroupType": "optional",
            "bidCount": "optional",  # auctions only
            "currentBidPrice": "optional",
            "watchCount": "restricted",  # requires eBay App Check grant
            "soldPrice": "not_in_api",
            "soldDate": "not_in_api",
            "totalSoldQuantity": "not_in_api",
        },
        # Keys here match the attribute names stored by the collector's detail
        # extractor (snake_case projections of the getItem payload).
        "detail": {
            "estimated_availabilities": "expected",
            "localized_aspects": "expected",
            "seller_item_revision": "optional",
            "gtin": "optional",
            "epid": "optional",
            "mpn": "optional",
            "brand": "optional",
            "unique_bidder_count": "optional",
            "bid_count": "optional",
            "return_terms": "optional",
            "ship_to_locations": "optional",
            "confirmedSalePrice": "not_in_api",
            "exactSoldQuantity": "not_in_api",
        },
    },
    "stockx": {
        "search": {
            "productId": "required",
            "title": "required",
            "urlKey": "expected",
            "styleId": "optional",
            "productType": "optional",
            "brand": "optional",
            "productAttributes": "optional",
            "soldPrice": "not_in_api",
            "saleCount": "not_in_api",
            "listingDate": "not_in_api",
        },
        "market_data": {
            "variantId": "required",
            "lowestAskAmount": "expected",
            "highestBidAmount": "optional",
            "sellFasterAmount": "optional",
            "earnMoreAmount": "optional",
            "standardMarketData": "optional",
            "flexMarketData": "optional",
            "lastSalePrice": "not_in_api",
            "salesCount": "not_in_api",
        },
        "variants": {
            "variantId": "required",
            "variantValue": "expected",
            "variantName": "expected",
            "gtins": "optional",
            "sizeChart": "optional",
        },
    },
}
