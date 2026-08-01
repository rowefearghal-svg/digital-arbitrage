# PUE v0.1 Live Shadow Trial — Operational Runbook

## Purpose

This command runs a controlled, read-only, post-release live shadow trial of the
released PUE v0.1 vertical slice against real eBay and StockX search results.
It does **not** modify the commercial arbitrage pipeline, recommendations,
pricing or purchasing behaviour. It produces a human-review queue and structured
reports for observational analysis.

## Command

```bash
arb pue live-shadow \
  --queries data/pue/trials/gpu_live_shadow_queries_v0.1.json \
  --provider ebay_browse \
  --provider stockx \
  --max-results-per-query 25 \
  --output-dir var/pue/live-shadow
```

If `--queries` is omitted, the default GPU manifest is used. If `--provider` is
omitted, every provider listed in the manifest is tried.

## Required environment variables

Credentials are read from the environment exactly as the existing `arb scan` and
`arb auth stockx` commands do. Do not commit credentials.

- `EBAY_BROWSE_APP_ID`, `EBAY_BROWSE_CERT_ID`, `EBAY_BROWSE_OAUTH_SCOPE`
- `STOCKX_CLIENT_ID`, `STOCKX_REDIRECT_URI`

StockX requires a one-time browser OAuth flow:

```bash
arb auth stockx
```

This creates a cached token in the user home directory. The live-shadow command
reuses that cache.

## Credential-safety rules

- No token, cookie, password or API secret is written to the trial reports or
  the PUE shadow database.
- Live listing titles and raw provider responses are not committed to Git.
- All local output lives under `var/pue/live-shadow/`, which is in `.gitignore`.
- Seller personal data, images and raw descriptions are not persisted.
- Logs and exception messages are redacted by the live-provider framework.

## Local output locations

Default:

```
var/pue/live-shadow/
  <run_id>_run_manifest.json
  <run_id>_acquisition_report.json
  <run_id>_pue_distribution.json
  <run_id>_review_queue.json
  <run_id>_review_queue.md
  <run_id>_run_report.md
  <run_id>_pue_shadow.db
```

## Report fields

- `*_run_manifest.json`: run id, times, manifest id/hash, providers requested
  and contacted, PUE release manifest hash, schema versions, output file paths,
  status, known limitations.
- `*_acquisition_report.json`: per (query, provider) requested/returned counts,
  normalized count, PUE case count, latency, failure category.
- `*_pue_distribution.json`: Decision, product-form, identification-level,
  comparability and classifier/PUE disagreement distributions by provider and in
  aggregate, latency percentiles.
- `*_review_queue.json`/`.md`: prioritized list of cases for human review.

## Rerun behaviour

Each run gets a fresh `run_id` and writes a new set of files. The PUE shadow
persistence table uses the case-equivalence key from the existing PUE case store,
so identical listing/search context pairs will not accumulate duplicate records.

## Partial-run interpretation

A `PARTIAL_SUCCESS` status means at least one provider or query succeeded while
another failed. A `FAILURE` means no provider succeeded for any query. A provider
returning zero marketplace results is valid data and is reported as zero coverage,
not a technical failure.

## How to review queued cases

Open `<run_id>_review_queue.md` or `<run_id>_review_queue.json`. Each item
contains the raw/normalized title, classifier label, PUE Decision, product form,
identification level, comparability, explanation and a set of blank
`review_fields`. Human reviewers should fill those in; the implementation does
not pre-populate them as ground truth.

## How to delete locally retained trial data

```powershell
Remove-Item -Recurse -Force var/pue/live-shadow
```

This removes all reports and the PUE shadow database. It does not affect
version-controlled release artifacts or the main PUE benchmark dataset.

## Known eBay and StockX limitations

- eBay Browse `q=` is capped at 100 characters and disallows wildcards.
- eBay may return zero results for a query; this is recorded, not treated as a
  pipeline failure.
- StockX is primarily a sneaker/streetwear marketplace and may legitimately
  return zero GPU results; this is a provider-coverage finding, not an
  implementation defect.
- StockX catalog results are product-level, not marketplace listings, and may
  contain a single price/variant summary rather than condition-specific pricing.
