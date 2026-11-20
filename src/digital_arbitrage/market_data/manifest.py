"""Collection manifest: a bounded, versioned product-family query set.

Mirrors the live-shadow ``QueryManifest`` shape (``manifest_id``, ``version``,
``queries[]``) so operators can reuse the same mental model, extended with
per-query request options the collector honours:

.. code-block:: json

    {
      "manifest_id": "gpu-collection-v0.1",
      "version": "0.1.0",
      "queries": [
        {
          "query_id": "q-rtx-4090",
          "search_text": "RTX 4090",
          "providers": ["ebay_browse", "stockx"],
          "max_results_per_provider": 50,
          "detail_top_n": 20
        }
      ]
    }

``detail_top_n`` caps eBay ``getItem`` enrichment for that query (the run-wide
``detail_fetch_top_n`` budget still applies across all queries).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """The collection manifest is malformed."""


@dataclass(frozen=True, slots=True)
class CollectionQuery:
    query_id: str
    search_text: str
    providers: tuple[str, ...]
    max_results_per_provider: int | None = None
    #: eBay getItem calls for this query: None = inherit the run budget,
    #: 0 = no detail enrichment for this query.
    detail_top_n: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CollectionManifest:
    manifest_id: str
    version: str
    queries: tuple[CollectionQuery, ...]
    description: str | None = None

    @property
    def manifest_hash(self) -> str:
        canonical = json.dumps(
            {
                "manifest_id": self.manifest_id,
                "version": self.version,
                "queries": [
                    {
                        "query_id": q.query_id,
                        "search_text": q.search_text,
                        "providers": list(q.providers),
                        "max_results_per_provider": q.max_results_per_provider,
                        "detail_top_n": q.detail_top_n,
                    }
                    for q in self.queries
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_collection_manifest(path: str | Path) -> CollectionManifest:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    except ValueError as exc:
        raise ManifestError(f"manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError("manifest root must be an object")

    manifest_id = raw.get("manifest_id")
    if not isinstance(manifest_id, str) or not manifest_id:
        raise ManifestError("manifest_id is required")
    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise ManifestError("version is required")
    queries_raw = raw.get("queries")
    if not isinstance(queries_raw, list) or not queries_raw:
        raise ManifestError("queries must be a non-empty list")

    queries: list[CollectionQuery] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(queries_raw):
        if not isinstance(entry, dict):
            raise ManifestError(f"queries[{index}] must be an object")
        query_id = entry.get("query_id")
        search_text = entry.get("search_text")
        if not isinstance(query_id, str) or not query_id:
            raise ManifestError(f"queries[{index}].query_id is required")
        if query_id in seen_ids:
            raise ManifestError(f"duplicate query_id {query_id!r}")
        seen_ids.add(query_id)
        if not isinstance(search_text, str) or not search_text.strip():
            raise ManifestError(f"queries[{index}].search_text is required")
        providers = entry.get("providers")
        if (
            not isinstance(providers, list)
            or not providers
            or not all(isinstance(p, str) for p in providers)
        ):
            raise ManifestError(f"queries[{index}].providers must be a non-empty list")
        max_results = entry.get("max_results_per_provider")
        if max_results is not None and (not isinstance(max_results, int) or max_results <= 0):
            raise ManifestError(f"queries[{index}].max_results_per_provider must be a positive int")
        detail_top_n = entry.get("detail_top_n")
        if detail_top_n is not None and (not isinstance(detail_top_n, int) or detail_top_n < 0):
            raise ManifestError(f"queries[{index}].detail_top_n must be a non-negative int")
        queries.append(
            CollectionQuery(
                query_id=query_id,
                search_text=search_text.strip(),
                providers=tuple(providers),
                max_results_per_provider=max_results,
                detail_top_n=detail_top_n,
                extra={
                    k: v
                    for k, v in entry.items()
                    if k
                    not in {
                        "query_id",
                        "search_text",
                        "providers",
                        "max_results_per_provider",
                        "detail_top_n",
                    }
                },
            )
        )
    description = raw.get("description")
    return CollectionManifest(
        manifest_id=manifest_id,
        version=version,
        queries=tuple(queries),
        description=description if isinstance(description, str) else None,
    )
