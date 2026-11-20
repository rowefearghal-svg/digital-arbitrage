"""Data model for the market-data collection & storage layer.

Provider identity is kept provider-native and entity types are kept distinct:
an eBay ``listing``, a StockX ``catalogue_product``, a StockX ``variant`` and an
eBay ``item_group`` are different entity types that are never merged. The PUE's
inferred product identity is linked only through :class:`EntityLink` rows.

Conventions enforced here and in :mod:`.store`:

* Missing values are ``None``/NULL - never zero. A field the provider did not
  return is *unknown*, not ``0``.
* Asking prices (``PriceKind.ASK``), auction bids (``BID``), market quotes,
  retail prices and verified sale prices (``SOLD``) are different price kinds
  and are never conflated.
* ``ObservationState.DISAPPEARED`` means "was seen, then absent from a complete
  coverage re-run". It is never treated as evidence of a sale.
* ``estimatedSoldQuantity`` is stored as a *provider estimate*
  (``quantity_sold_estimate``), never as a confirmed transaction count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: Collector implementation version, stamped on every run row.
COLLECTOR_VERSION = "market-data-collector-0.1.0"
#: Observation/attribute extraction versions (bump when mapping changes).
EBAY_PARSER_VERSION = "ebay-browse-parser-0.1.0"
STOCKX_PARSER_VERSION = "stockx-parser-0.1.0"
#: Redaction algorithm version, stamped on every stored raw payload.
REDACTION_VERSION = "redaction-0.1.0"


class EntityType(StrEnum):
    """Provider-native entity kinds; deliberately distinct, never merged."""

    LISTING = "listing"  # eBay itemId
    CATALOGUE_PRODUCT = "catalogue_product"  # StockX productId
    VARIANT = "variant"  # StockX variantId
    ITEM_GROUP = "item_group"  # eBay seller-defined variations group


class ObservationState(StrEnum):
    """Evidence quality classification of one observation."""

    ACTIVE = "active"
    CONFIRMED_SALE = "confirmed_sale"  # only from a sale-attesting source
    ENDED = "ended"  # provider says no longer purchasable
    DISAPPEARED = "disappeared"  # absent from a complete re-run; NOT a sale
    INFERRED_OUTCOME = "inferred_outcome"  # derived guess, never presented as fact
    UNKNOWN = "unknown"


class PriceKind(StrEnum):
    """What a price value means. Asking != achieved."""

    ASK = "ask"  # listing price / lowest ask
    BID = "bid"  # current auction bid / highest bid
    SOLD = "sold"  # verified achieved sale price (attesting source only)
    RETAIL = "retail"  # catalogue retail/MSRP
    GUIDANCE = "guidance"  # provider-derived suggestion (StockX sellFaster/earnMore)
    UNKNOWN = "unknown"


class SourceKind(StrEnum):
    """Which endpoint family produced the observation (kept distinguishable)."""

    SEARCH = "search"
    DETAIL = "detail"
    MARKET_DATA = "market_data"
    VARIANTS = "variants"
    MANUAL_IMPORT = "manual_import"


class TaskStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"


class LinkStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class VerificationStatus(StrEnum):
    """Provenance quality of a manual/external observation import."""

    UNVERIFIED = "unverified"
    SELF_REPORTED = "self_reported"
    CROSS_CHECKED = "cross_checked"


@dataclass(slots=True)
class CollectionTask:
    """One HTTP page/endpoint call within a collection run."""

    provider: str
    query_id: str
    query_text: str
    endpoint: str  # e.g. 'item_summary/search', 'item/{id}'
    page_number: int = 1
    offset: int = 0
    filters_json: str = "{}"
    marketplace: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    http_status: int | None = None
    error_category: str | None = None
    attempts: int = 0
    items_returned: int = 0
    items_stored: int = 0
    items_rejected: int = 0
    reported_total: int | None = None
    has_more: bool | None = None
    duration_ms: int | None = None
    retrieved_at: str | None = None
    task_id: int | None = None


@dataclass(slots=True)
class ProviderEntity:
    """A provider-native entity keyed by (provider, entity_type, native id)."""

    provider: str
    entity_type: EntityType
    provider_entity_id: str
    parent_entity_id: int | None = None
    marketplace: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    seller_key: str | None = None  # stable pseudonymous seller identifier
    latest_state: ObservationState = ObservationState.UNKNOWN
    entity_id: int | None = None


@dataclass(slots=True)
class Observation:
    """One timestamped evidence record for an entity. Append-only."""

    entity_id: int
    collection_run_id: str
    observed_at: str
    source_kind: SourceKind
    state: ObservationState
    attributes_json: str
    content_hash: str
    parser_version: str
    task_id: int | None = None
    source_event_time: str | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    price_kind: PriceKind = PriceKind.UNKNOWN
    quantity_available: int | None = None
    quantity_sold_estimate: int | None = None
    condition: str | None = None
    description: str | None = None
    observation_id: int | None = None


@dataclass(slots=True)
class IngestResult:
    """Per-item ingestion counters for a task."""

    stored: int = 0
    rejected: int = 0
    entity_ids: list[int] = field(default_factory=list)
