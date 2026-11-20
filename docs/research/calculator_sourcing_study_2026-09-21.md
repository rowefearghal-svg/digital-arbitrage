# Calculator Sourcing Study

**Date:** 2026-09-21  
**Project:** digital-arbitrage  
**Retrieval window:** 2026-09-21 (live collection + web research)  
**Currency assumption:** GBP/EUR ≈ 1.166 (EUR/GBP ≈ 0.8575, market rate on 2026-09-21).  
**Method:** Bounded data collection using the existing `arb collect` eBay Browse provider plus public web price checks. No PUE run, no orders, no account creation, no code changes. Raw payloads and the collection DB are kept outside Git.

## Executive summary

No calculator opportunity in the €5–€20 acquisition band survives realistic all-in economics for a small, unregistered Irish trial. The closest candidate is the **Casio fx-85GT CW+ (FX-85GTCWPLUS-W-UT)** from **Oxford Scientific Solutions** at £10.65 ex-VAT, but once inbound shipping, Irish import VAT, eBay business fees, outbound An Post postage and a returns allowance are included it needs a sale total of roughly **€31** to break even, while active asking prices are €20–€25. Margins are eroded by low absolute prices and high per-unit postage/fees.

For a VAT-registered trader who can recover import VAT and negotiate cheaper outbound fulfilment, the same model becomes marginal. For the project as configured, calculators do not currently look like a viable first arbitrage vertical.

## A. Marketplace & wholesaler coverage

| Source | URL | Access needed | Price visibility | Ireland delivery | Min order / MOQ | Integration options | Limitations |
|---|---|---|---|---|---|---|---|
| **eBay** (IE/GB/DE/US) | https://www.ebay.ie | Public; live via eBay Browse API | Public asks; VAT handling at checkout for cross-border | Seller-dependent; many GB sellers ship to IE | 1 unit | eBay Browse API already in `arb collect` (OAuth, `EBAY_CLIENT_ID/SECRET`) | No sold/closed price via Browse API; `soldPrice` not_in_api; only `estimatedSoldQuantity` as a sales estimate |
| **Amazon** (UK / DE) | https://www.amazon.co.uk | Public; seller account for resale | Public buy-box / marketplace offers | UK→IE post-Brexit adds import VAT/duty complexity; DE→IE is intra-EU | 1 unit | Product Advertising API or Selling Partner API (not connected; requires account + approval) | No live connector in repo; fees depend on category and fulfilment channel |
| **CEX Ireland** | https://ie.webuy.com | Public | Public cash/voucher buy and sell prices | IE store/online, click & collect or courier | 1 unit | No official API; Apify/community scrapers exist (not used) | Very limited calculator stock; grades vary |
| **Adverts.ie** | https://www.adverts.ie | Public (message to buy) | Public asking prices | Local / seller-arranged | 1 unit | No API; manual import only | No sold-price signal; buyer risk high; listings sparse for calculators |
| **DoneDeal** | https://www.donedeal.ie | Public (message to buy) | Public asking prices | Local / seller-arranged | 1 unit | No API; manual import only | Same limitations as Adverts.ie; calculators rare |
| **Oxford Scientific Solutions** | https://www.oxsci.co.uk | Public prices; trade/school account for invoice terms | Public ex-VAT price list | UK-based; IE delivery not quoted online; free UK shipping >£250 ex-VAT | 1 unit (price tiers 1-39 / 40-99 / 100+) | No API/CSV found; manual or email order | Need to contact for IE shipping, VAT, and customs handling |
| **121 Wholesale** | https://121wholesale.co.uk | No account required; trade account optional | Public ex-VAT prices | UK mainland only; IE not confirmed | No minimum order; free UK delivery >£250 | No API/CSV found; manual/web checkout | Need to verify IE shipping and whether they collect EU VAT at checkout |
| **RS Components Ireland** | https://ie.rs-online.com | Public prices; business account for free-delivery threshold | Public ex-VAT/inc-VAT | IE next-day available; free for logged-in business orders over threshold (≈£50/€50-€75 ex-VAT) | 1 unit | No public API found for small accounts; possible EDI for large trade customers | Prices are high for arbitrage; cheapest FX-85GTCW-W-UT is €19.76 ex-VAT |
| **Rapid Electronics** | https://www.rapidonline.com | Public prices; account for export setup | Public ex-VAT prices | Export to IE available; shipping quoted at checkout; no min order for export | 1 unit | No API/CSV found; manual/web order | UK source; import VAT/duty applies unless DDP/IOSS |
| **Viking Direct Ireland** | https://www.vikingdirect.ie | Public prices; account for order history | Public ex-VAT/inc-VAT | IE delivery; free over €75-€99 ex-VAT; otherwise ~€7.95-€7.99 | Tiered 1/2/3+ | No API/CSV found; manual/web order | Higher unit cost; easy IE fulfilment; good for reference pricing |

**Shortfall:** Only eBay has an existing, working API connector. Amazon would need a new API onboarding. The Irish/UK wholesalers have no discoverable public feeds; they would require manual price lists, CSV/XML trade feeds, or scraping outside the current collector.

## B. Shortlist of exact calculator models and offers

All prices are as observed on 2026-09-21 and exclude inbound delivery/tax unless stated. Used/refurbished/faulty units are separated.

| Model / MPN / EAN | Source | Condition | Unit price | Qty tier / MOQ | Delivery to IE | Total cash (1 unit) | Total cash (5 units) | Resale evidence (asks / solds) | Evidence limitations |
|---|---|---|---|---|---|---|---|---|---|
| **Casio fx-85GT CW+ Black**<br>MPN: FX-85GTCWPLUS-W-UT<br>EAN: 4549526620591 | Oxford Scientific Solutions | New | £10.65 ex-VAT (≈€12.42)<br>1-39 units | IE shipping not quoted; UK free >£250 ex-VAT | €12.42 + shipping + import VAT | €62.10 + shipping + import VAT | eBay active new €16.23–€20.78 (collector); eBay UK “trending at £12.93” for CW family; seller sold-est up to 1,206 for CW listings | No verified CW+ sold price; shipping & import VAT unknown for IE |
| **Casio fx-85GT CW+ Black**<br>FX-85GTCWPLUS-W-UT | Viking Direct Ireland | New | €16.59 ex-VAT (€20.41 inc-VAT) for 3+<br>€18.59 ex-VAT for 1 | Free IE delivery >€75-€99 ex-VAT; otherwise €7.95-€7.99 | €22.87 (1 inc-VAT + delivery) | €102.05 (5 inc-VAT, likely free delivery) | eBay active new €16–€20 (collector) | Same as above; high acquisition cost |
| **Casio FX-85GT CW Black**<br>MPN: FX-85GTCW-W-UT<br>EAN: 4549526615542 | Rapid Electronics | New | £12.90 ex-VAT (≈€15.04)<br>1+ | Export to IE; shipping quoted at checkout | €15.04 + shipping + import VAT | €75.21 + shipping + import VAT | eBay active new €14.50–€15.52; used €12.82 (collector) | Sold-price evidence sparse; import VAT applies |
| **Casio FX-85GT CW Black**<br>FX-85GTCW-W-UT | 121 Wholesale | New | £11.50 ex-VAT (≈€13.41)<br>no MOQ | UK mainland; IE not confirmed | €13.41 + shipping + import VAT | €67.05 + shipping + import VAT | Same as above | IE shipping & VAT unknown |
| **Casio FX-991EX**<br>MPN: FX-991EX-S-UT<br>EAN: 4549526603327 | eBay IE/GB/DE/US (via collector) | Used from €18.96 (GB); New from €33.30 (DE); German/Chinese variants mixed | 1 unit | Seller-dependent; cross-border VAT likely collected at checkout for ≤€150 items | ~€18.96 + shipping + possible import VAT | N/A (per-unit purchase) | eBay sold: £23.88 on 7 Sep 2026 (2 sold); active used €18.96–€27.24; active new €33.30+ | Sold price is one listing, not a distribution; “sold” dates from web search only; variants (DE/UK/US/Chinese) not identical |
| **Casio fx-83GT CW+ Black**<br>MPN: FX-83GTCWPLUS-W-UT<br>EAN: 4549526619335 | eBay IE (collector) | Used (slightly) | €10.00<br>1 unit | Seller local/arranged | ~€10.00 + local delivery | N/A | Retail new €19.99–€24.99 (Bookstation / O’Mahony’s) | Single used listing; no sold evidence; reselling a used unit at retail unlikely |

## C. Promising model/supplier combinations (ranked)

> **Note:** All three are “promising” only in the sense that they are the least unfavourable. Realistic all-in costs push every one below break-even for an unregistered seller.

### 1. Casio fx-85GT CW+ Black — Oxford Scientific Solutions
- **Why it ranks first:** Lowest wholesale unit price found (£10.65 / ≈€12.42 ex-VAT), exact MPN/EAN, new condition, and strong sales-velocity signal (CW-family listings with `estimatedSoldQuantity` up to 1,206 on eBay GB).
- **Break-even:** At an estimated landed cost of ~€18.01/unit (5-unit order, £10 shipping, 23% Irish import VAT), a sale total of **€31** is needed before the model becomes profitable.
- **Still to verify:**
  - IE shipping quote and whether Oxford ships DDP/IOSS or leaves import VAT to the courier.
  - Whether the buyer is VAT-registered and can recover import VAT.
  - Actual achieved (not asking) sale prices for the CW+ model on eBay IE/UK.
  - eBay IE business final-value fee category for calculators.

### 2. Casio FX-991EX — eBay GB/IE used listings
- **Why it ranks second:** Higher absolute price leaves more headroom for fees; one verified eBay UK sale at £23.88 (≈€27.84) on 7 Sep 2026, and active used asks from €18.96.
- **Break-even:** With landed cost around €22–€24 and the same fee model, a sale total of **€35+** is needed.
- **Still to verify:**
  - Exact condition and whether the unit is the UK-approved version (not German/Chinese).
  - Shipping + eBay-collected VAT to Ireland for cross-border orders.
  - More sold comparables; one sale is insufficient to set a reliable resale expectation.

### 3. Casio fx-85GT CW+ Black — Viking Direct Ireland
- **Why it ranks third:** No cross-border import unknowns (Irish VAT already in price), next-day IE delivery, and free shipping likely at a 5-unit order. Serves as a conservative “ceiling” acquisition cost.
- **Break-even:** Landed cost ~€20.41/unit (inc-VAT); needs a sale total of **€34**.
- **Still to verify:**
  - Exact free-delivery threshold and whether the 3+ tier applies to a mixed-colour order.
  - Whether eBay buyers will pay €28–€30+ for this model when active asks are €16–€20.

## D. Most worthwhile sources to integrate next

Judged by useful coverage, economics, and access—not by connector count:

1. **eBay GB/DE marketplace variants via the existing collector.** The connector already works; simply switching `ebay_marketplace_id` to `EBAY_GB` or `EBAY_DE` expands buy-side coverage without building a new adapter. This is the highest-ROI next step.
2. **Amazon (Selling Partner API or Product Advertising API).** It is the largest marketplace with both buy and sell data. It requires account/approval and is not free, but it is the only other major marketplace that could support a real arbitrage loop.
3. **A trade price-feed from one Irish/UK B2B office supplier** (e.g., Viking Direct, RS Components, or Oxford Scientific). If a CSV/XML feed or FTP price list can be obtained, a generic `manual_import` adapter would be more useful than scraping public HTML, because wholesaler prices change less frequently and are the primary buy-side signal.

CEX, Adverts.ie, and DoneDeal are not recommended for integration first: they lack APIs, have thin calculator inventory, and provide no sold-price signal.

## E. Recommendation — first PUE matching rules to add and validate

Do **not** run the existing GPU-specific PUE on calculators. Instead, seed a calculator product catalogue first, then validate PUE matching on the titles returned by `arb collect`.

1. **Add canonical catalogue entries for:**
   - `Casio fx-85GT CW+ Black` — MPN `FX-85GTCWPLUS-W-UT`, EAN `4549526620591`
   - `Casio fx-85GT CW Black` — MPN `FX-85GTCW-W-UT`, EAN `4549526615542`
   - `Casio fx-83GT CW+ Black` — MPN `FX-83GTCWPLUS-W-UT`, EAN `4549526619335`
   - `Casio FX-991EX` — MPN `FX-991EX-S-UT`, EAN `4549526603327`
2. **Add exclusion / classification rules:**
   - Reject `Wyngs`, `protective case`, `cover`, and titles containing `Getling` (book) as accessories/non-product.
   - Flag regional variants (`FX-991DE X`, `Chinese functions`, `German version`) as separate products, not matches for the UK/Ireland model.
   - Distinguish `fx-85GT X` (older) from `fx-85GT CW`/`CW+` (newer ClassWiz) by title/MPN.
3. **Validation approach:** Run a small `arb collect` for each model, feed observations to the PUE in shadow mode, and compare the inferred product identity against the seeded MPN/EAN. Only after the shadow benchmark passes should PUE matching affect deduplication or scoring.

## Cost model used for economics

All calculations are provisional and use the following conservative assumptions:
- **Inbound landed cost** = unit price + per-unit shipping + Irish import VAT at 23% on (goods + shipping). For UK wholesalers, import VAT is treated as non-recoverable unless the buyer is VAT-registered.
- **Resale channel:** eBay IE as a business seller.
- **eBay fee:** 12.8% of total sale amount (item + buyer postage) + €0.35 per order, based on eBay UK business seller guidance.
- **Outbound postage:** An Post domestic packet ~€5.50 (250 g class; actual depends on dimensions).
- **Packaging:** €1.50 per unit.
- **Returns allowance:** 5% of gross sale.

### Example: Oxford Scientific FX-85GT CW+ (5-unit order)

| Line | Amount (EUR) |
|---|---|
| 5 × £10.65 ex-VAT @ 1.166 | 62.10 |
| Inbound shipping (provisional £10/order) | 11.66 |
| Irish import VAT 23% on €73.76 | 16.96 |
| **Landed cost per unit** | **18.01** |
| Needed sale total to break even* | ~31.00 |

*Break-even solves: `sale_total × (1 – 0.128 – 0.05) – 0.35 – 5.50 – 1.50 – 18.01 = 0`.

## References

- eBay UK private/business seller fees: https://www.ebay.co.uk/help/selling/fees-credits-invoices/fees-private-sellers-activated-managed-payments?id=4822
- Amazon UK seller pricing: https://sell.amazon.co.uk/pricing
- An Post postal rates Feb 2026: https://www.anpost.com/getmedia/15a8b2c8-79cb-44a0-9482-06042e9b1388/Guide-Postal-Rates-Feb2026.pdf
- Oxford Scientific Solutions FX-85GT CW+: https://www.oxsci.co.uk/buy-online/calculators/casio-fx-85gtcw--scientific-calculator-black
- 121 Wholesale FX85 GTcw: https://121wholesale.co.uk/products/casio-fx85-gtcw-scientific-calculator
- Rapid Electronics calculator range: https://www.rapidonline.com/casio-fx-83gtcw-fx-85gtcw-fx991cw-classwiz-scientific-calculator-range-589130
- RS Components Ireland FX-85GTCW-W-UT: https://ie.rs-online.com/web/p/calculators/2655146
- Viking Direct Ireland FX-85GT CW+: https://www.vikingdirect.ie/en/casio-plus-w-scientific-calculator-digit-display-black-battery-fx-85gtcw-p-1273492
- Live collection DB: `C:\Users\fearg\.digital_arbitrage\calculator_research_ie.db` (run `collect-20260921T172640Z-dd975616`) — kept out of Git.

---

**Delivered by:** Devin  
**Status:** Research complete; report saved. No code changes, orders, accounts, or commits made.
