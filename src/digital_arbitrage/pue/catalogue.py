"""The seed candidate catalogue and its repository implementation.

Reasoning components (retrieval, evaluation) must not parse catalogue files
or contain direct SQL (spec section 13). ``JsonCandidateRepository`` is the
only component that touches the JSON file; everything else talks to the
:class:`CandidateRepository` protocol.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from .canonical import canonical_file_hash
from .enums import ProductForm
from .models import CandidateQuery, CatalogueProduct
from .validation import PueValidationError

#: Default location of the hand-seeded v0.1 catalogue (spec section 12.1).
DEFAULT_CATALOGUE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "pue" / "catalogues" / "gpu_seed_v0.1.json"
)


def catalogue_file_hash(path: Path | str = DEFAULT_CATALOGUE_PATH) -> str:
    """Stable, cross-platform SHA-256 hash of the catalogue's *canonical
    JSON content* (see :mod:`digital_arbitrage.pue.canonical`) - not the
    raw file bytes, which would vary with CRLF/LF line-ending conversion or
    incidental whitespace/key ordering (Sprint 3 pre-merge correction item
    4). Recorded in release manifests so a release is bound to the exact
    catalogue content that produced it."""
    return canonical_file_hash(path)


#: Suffixes that mark a family name as a mobile/laptop variant of a base
#: desktop family (e.g. "rtx 4090 laptop gpu" -> "rtx 4090"). Stripping them
#: lets retrieval treat the desktop and mobile variants of the same chip as
#: a related pool - Candidate Evaluation is where the mobile-vs-desktop hard
#: contradiction (spec 15.6-style rule) is actually enforced; retrieval must
#: stay permissive enough to surface the contradiction in the first place
#: (mirrors the existing product-form permissiveness in this method).
_MOBILE_FAMILY_SUFFIXES = (" laptop gpu", " laptop", " mobile")


def _base_family(name: str) -> str:
    lowered = name.strip().lower()
    for suffix in _MOBILE_FAMILY_SUFFIXES:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)]
    return lowered


class RetrievedCatalogueProduct(Protocol):
    """Structural type returned by repository ``retrieve`` (spec section 13)."""

    product: CatalogueProduct
    matched_fields: tuple[str, ...]


class CandidateRepository(Protocol):
    """Contract for retrieving :class:`CatalogueProduct` records (spec 13)."""

    def get_by_id(self, catalogue_product_id: str) -> CatalogueProduct | None: ...

    def get_by_identifier(
        self, *, identifier_type: str, value: str, knowledge_version: str
    ) -> Sequence[CatalogueProduct]: ...

    def retrieve(
        self, *, query: CandidateQuery, limit: int, knowledge_version: str
    ) -> Sequence[CatalogueProduct]: ...

    def all_products(self, knowledge_version: str) -> Sequence[CatalogueProduct]: ...


def _product_from_json(entry: Mapping[str, object], knowledge_version: str) -> CatalogueProduct:
    """Build one :class:`CatalogueProduct` from a raw JSON entry.

    Any malformed entry - a missing required field, an invalid enum value
    (e.g. an unrecognized ``product_form``), or a field of the wrong type -
    must surface as :class:`PueValidationError`, never as an uncaught
    ``KeyError``/``ValueError``/``TypeError``: default processing must
    convert an unusable catalogue into PROCESSING_FAILED /
    CATALOGUE_UNAVAILABLE (see orchestration.process_one), not crash
    (pre-merge correction).
    """
    if not isinstance(entry, Mapping):
        raise PueValidationError(f"catalogue entry must be an object, got {type(entry).__name__}")

    identifier = entry.get("catalogue_product_id", "<unknown>")
    try:
        identifiers_raw = entry.get("identifiers", {})
        if not isinstance(identifiers_raw, Mapping):
            raise PueValidationError("catalogue entry 'identifiers' must be an object")
        identifiers = {str(k): tuple(v) for k, v in identifiers_raw.items()}

        attributes_raw = entry.get("attributes", {})
        if not isinstance(attributes_raw, Mapping):
            raise PueValidationError("catalogue entry 'attributes' must be an object")

        return CatalogueProduct(
            catalogue_product_id=str(entry["catalogue_product_id"]),
            canonical_title=str(entry["canonical_title"]),
            brand=str(entry["brand"]),
            chipset_manufacturer=(
                str(entry["chipset_manufacturer"]) if entry.get("chipset_manufacturer") else None
            ),
            family=str(entry["family"]),
            model=str(entry["model"]),
            variant=(str(entry["variant"]) if entry.get("variant") else None),
            product_form=ProductForm(str(entry["product_form"])),
            product_type=str(entry["product_type"]),
            identifiers=identifiers,
            aliases=tuple(str(a) for a in entry.get("aliases", ())),  # type: ignore[attr-defined]
            attributes=dict(attributes_raw),
            compatibility_targets=tuple(
                str(c)
                for c in entry.get("compatibility_targets", ())  # type: ignore[attr-defined]
            ),
            knowledge_version=str(entry.get("knowledge_version", knowledge_version)),
        )
    except PueValidationError:
        raise
    except (KeyError, ValueError, TypeError) as exc:
        raise PueValidationError(f"malformed catalogue entry {identifier!r}: {exc}") from exc


def load_catalogue(path: Path | str = DEFAULT_CATALOGUE_PATH) -> tuple[CatalogueProduct, ...]:
    """Load and validate the JSON catalogue file into :class:`CatalogueProduct`."""
    resolved = Path(path)
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PueValidationError(f"could not read catalogue file {resolved}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PueValidationError(f"catalogue file {resolved} is not valid JSON: {exc}") from exc

    knowledge_version = str(raw.get("knowledge_version", ""))
    products_raw = raw.get("products", [])
    if not isinstance(products_raw, list):
        raise PueValidationError("catalogue file 'products' must be a list")
    return tuple(_product_from_json(entry, knowledge_version) for entry in products_raw)


class JsonCandidateRepository:
    """In-memory :class:`CandidateRepository` backed by the seed JSON catalogue."""

    def __init__(self, products: Sequence[CatalogueProduct] | None = None) -> None:
        self._products: tuple[CatalogueProduct, ...] = (
            tuple(products) if products is not None else load_catalogue()
        )
        self._by_id: dict[str, CatalogueProduct] = {
            p.catalogue_product_id: p for p in self._products
        }

    @classmethod
    def from_path(cls, path: Path | str = DEFAULT_CATALOGUE_PATH) -> JsonCandidateRepository:
        return cls(load_catalogue(path))

    def all_products(self, knowledge_version: str) -> Sequence[CatalogueProduct]:
        return tuple(p for p in self._products if p.knowledge_version == knowledge_version)

    def get_by_id(self, catalogue_product_id: str) -> CatalogueProduct | None:
        return self._by_id.get(catalogue_product_id)

    def get_by_identifier(
        self, *, identifier_type: str, value: str, knowledge_version: str
    ) -> Sequence[CatalogueProduct]:
        normalized = value.strip().lower()
        matches = []
        for product in self._products:
            if product.knowledge_version != knowledge_version:
                continue
            values = product.identifiers.get(identifier_type, ())
            if any(v.strip().lower() == normalized for v in values):
                matches.append(product)
        return tuple(matches)

    def retrieve(
        self, *, query: CandidateQuery, limit: int, knowledge_version: str
    ) -> Sequence[CatalogueProduct]:
        """Structured filter pass (stage 2). Missing fields never exclude.

        Explicit incompatible fields (family, product_form, product_type)
        may exclude a Candidate. This method does not fuzzy-rank; ranking is
        performed by :mod:`digital_arbitrage.pue.retrieval`.
        """
        # Product form/type is deliberately NOT a hard exclusion here: a
        # highly similar complete-product Candidate for a water-block
        # hypothesis must still be retrievable so Candidate Evaluation can
        # demonstrate the hard product-form rejection (spec section 15.6
        # worked example; retrieval/evaluation separation invariant). Family
        # is the hard filter field for this stage; product_type is used only
        # when there is no family signal at all (e.g. a generic "graphics
        # card" listing), to keep the candidate pool relevant.
        results = []
        for product in self._products:
            if product.knowledge_version != knowledge_version:
                continue
            if query.family is not None:
                if (
                    product.family != query.family
                    and query.family not in product.compatibility_targets
                    and _base_family(product.family) != _base_family(query.family)
                ):
                    continue
            elif query.product_type is not None:
                if product.product_type != query.product_type:
                    continue
            results.append(product)
            if len(results) >= limit:
                break
        return tuple(results)
