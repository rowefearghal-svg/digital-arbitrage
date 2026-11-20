"""Market-data collection & storage layer.

Manifest-driven, read-only collection from the existing live providers into a
durable, append-only SQLite store. See
``docs/MARKET_DATA_COLLECTION_DESIGN.md`` for the design.
"""

from .collector import DEFAULT_MARKET_DB, CollectionConfig, CollectionRunner
from .manifest import CollectionManifest, CollectionQuery, load_collection_manifest
from .models import (
    EntityType,
    ObservationState,
    PriceKind,
    SourceKind,
    TaskStatus,
)
from .store import MarketDataStore

__all__ = [
    "CollectionConfig",
    "CollectionManifest",
    "CollectionQuery",
    "CollectionRunner",
    "DEFAULT_MARKET_DB",
    "EntityType",
    "MarketDataStore",
    "ObservationState",
    "PriceKind",
    "SourceKind",
    "TaskStatus",
    "load_collection_manifest",
]
