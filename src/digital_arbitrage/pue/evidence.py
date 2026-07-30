"""Deterministic Evidence extraction from an Observation's title text.

Extraction is title-first (spec 3.3) and bounded (spec 9.5): a token is
emitted only when it belongs to a defined :class:`EvidenceType` or a known
term group loaded from the versioned knowledge artifact
``data/pue/knowledge/gpu_terms_v0.1.json``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from .enums import EvidencePolarity, EvidenceType
from .models import Evidence, Observation, ProcessingContext

DEFAULT_TERMS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "pue" / "knowledge" / "gpu_terms_v0.1.json"
)

_MPN_RE = re.compile(r"\b[A-Z0-9]+(?:[-/][A-Z0-9]+){1,6}\b")
_GTIN_RE = re.compile(r"\b\d{8,14}\b")
_CAPACITY_RE = re.compile(r"\b(\d{1,3})\s?(gb|mb)\b", re.IGNORECASE)

_EXTRACTION_METHOD = "gpu_terms_deterministic_v0.1"


@lru_cache(maxsize=4)
def load_terms(path: str = str(DEFAULT_TERMS_PATH)) -> Mapping[str, object]:
    """Load and cache the versioned term-group knowledge artifact."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _find_all(haystack_lower: str, needle: str) -> list[tuple[int, int]]:
    """Return non-overlapping (start, end) spans of ``needle`` in ``haystack_lower``."""
    spans: list[tuple[int, int]] = []
    start = 0
    needle_lower = needle.lower()
    if not needle_lower:
        return spans
    while True:
        idx = haystack_lower.find(needle_lower, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(needle_lower)))
        start = idx + len(needle_lower)
    return spans


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(span[0] < t[1] and t[0] < span[1] for t in taken)


def _emit(
    *,
    observation: Observation,
    context: ProcessingContext,
    evidence_type: EvidenceType,
    raw_value: str,
    normalized_value: str | int | float | bool | None,
    source_field: str,
    span: tuple[int, int] | None,
    polarity: EvidencePolarity | None,
    confidence: float | None = 1.0,
) -> Evidence:
    start, end = span if span is not None else (None, None)
    return Evidence(
        evidence_id=context.id_factory(),
        observation_id=observation.observation_id,
        evidence_type=evidence_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        source_field=source_field,
        source_start=start,
        source_end=end,
        extraction_method=_EXTRACTION_METHOD,
        extraction_confidence=confidence,
        polarity_hint=polarity,
        capability_version=context.capability_version,
    )


def _match_term_group(
    text_lower: str, terms: Sequence[str], taken: list[tuple[int, int]]
) -> list[tuple[str, tuple[int, int]]]:
    """Match a flat phrase list, longest phrase first, avoiding span overlap.

    Deduplicates via ``dict.fromkeys`` (order-preserving) rather than
    ``set()``: Python's string-hash randomization would otherwise make the
    relative order of equal-length phrases vary run to run, breaking
    determinism (regression found during Sprint 1 implementation).
    """
    matches: list[tuple[str, tuple[int, int]]] = []
    for phrase in sorted(dict.fromkeys(terms), key=lambda p: (-len(p), p)):
        for span in _find_all(text_lower, phrase):
            if _overlaps(span, taken):
                continue
            matches.append((phrase, span))
            taken.append(span)
    return matches


def extract_evidence(observation: Observation, context: ProcessingContext) -> tuple[Evidence, ...]:
    """Extract deterministic Evidence from ``observation.normalized_title``."""
    terms = load_terms()
    text = observation.normalized_title or ""
    text_lower = text.lower()
    evidence: list[Evidence] = []
    taken_spans: list[tuple[int, int]] = []

    if not text.strip():
        return tuple()

    # -- brand -------------------------------------------------------- #
    brand_aliases: Mapping[str, list[str]] = terms.get("brand_aliases", {})  # type: ignore[assignment]
    for brand, aliases in brand_aliases.items():
        for _phrase, span in _match_term_group(text_lower, aliases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.BRAND_TOKEN,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=brand,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )

    # -- accessory / component / replacement-part terms (checked BEFORE
    #    family/model and the generic product_type_terms block below so a
    #    specific phrase like "gpu fan"/"gpu block"/"gpu holder" is never
    #    suppressed by the broad, overlapping "gpu" token: whichever match
    #    claims a character span first wins, and a specific term must win
    #    over a broad one - spec 9.5/10.1 precedence). -------------------- #
    accessory_terms: Mapping[str, list[str]] = terms.get("accessory_component_terms", {})  # type: ignore[assignment]
    for ptype, phrases in accessory_terms.items():
        for _phrase, span in _match_term_group(text_lower, phrases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.PRODUCT_FORM_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=ptype,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.PRODUCT_TYPE_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=ptype,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )

    # -- box-included terms (must be checked BEFORE packaging terms so
    #    "box included" is never misread as "box only") ------------------ #
    box_included_terms: list[str] = terms.get("box_included_terms", [])  # type: ignore[assignment]
    for _phrase, span in _match_term_group(text_lower, box_included_terms, taken_spans):
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.PACKAGING_TERM,
                raw_value=text[span[0] : span[1]],
                normalized_value="box_included",
                source_field="normalized_title",
                span=span,
                polarity=EvidencePolarity.QUALIFYING,
            )
        )

    # -- packaging-only terms ------------------------------------------- #
    packaging_terms: list[str] = terms.get("packaging_terms", [])  # type: ignore[assignment]
    for _phrase, span in _match_term_group(text_lower, packaging_terms, taken_spans):
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.PACKAGING_TERM,
                raw_value=text[span[0] : span[1]],
                normalized_value="packaging_only",
                source_field="normalized_title",
                span=span,
                polarity=EvidencePolarity.CONTRADICTING,
            )
        )

    # -- exclusion terms (checked BEFORE compatibility phrases so "for
    #    parts" is never partially consumed by a generic "for" match) ----- #
    exclusion_terms: Mapping[str, list[str]] = terms.get("exclusion_terms", {})  # type: ignore[assignment]
    for reason, phrases in exclusion_terms.items():
        for _phrase, span in _match_term_group(text_lower, phrases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.EXCLUSION_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=reason,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.CONTRADICTING,
                )
            )

    # -- compatibility phrases ------------------------------------------- #
    compatibility_terms: list[str] = terms.get("compatibility_terms", [])  # type: ignore[assignment]
    for phrase, span in _match_term_group(text_lower, compatibility_terms, taken_spans):
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.COMPATIBILITY_TERM,
                raw_value=text[span[0] : span[1]],
                normalized_value=phrase.strip(),
                source_field="normalized_title",
                span=span,
                polarity=EvidencePolarity.QUALIFYING,
            )
        )

    # -- bundle terms ------------------------------------------------------ #
    bundle_terms: list[str] = terms.get("bundle_terms", [])  # type: ignore[assignment]
    for phrase, span in _match_term_group(text_lower, bundle_terms, taken_spans):
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.BUNDLE_TERM,
                raw_value=text[span[0] : span[1]],
                normalized_value=phrase.strip(),
                source_field="normalized_title",
                span=span,
                polarity=EvidencePolarity.QUALIFYING,
            )
        )

    # -- family / model (longest alias first, across all families). Checked
    #    AFTER all the specific categories above so an explicit accessory/
    #    packaging/exclusion/compatibility/bundle phrase always wins a
    #    contested character span over a family mention (spec 9.5/10.1). --- #
    families: Mapping[str, list[str]] = terms.get("families", {})  # type: ignore[assignment]
    flat_family_aliases: list[tuple[str, str]] = [
        (alias, family) for family, aliases in families.items() for alias in aliases
    ]
    for alias, family in sorted(flat_family_aliases, key=lambda t: len(t[0]), reverse=True):
        for span in _find_all(text_lower, alias):
            if _overlaps(span, taken_spans):
                continue
            taken_spans.append(span)
            raw = text[span[0] : span[1]]
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.PRODUCT_FAMILY_TOKEN,
                    raw_value=raw,
                    normalized_value=family,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.MODEL_TOKEN,
                    raw_value=raw,
                    normalized_value=family,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )

    # -- product-type / complete-product hint terms (generic "gpu"/
    #    "graphics card"/"video card" etc.; checked LAST among the phrase
    #    categories above so it can never suppress a more specific
    #    accessory/packaging/exclusion/compatibility/bundle/family match -
    #    spec 9.5/10.1 precedence). ---------------------------------------- #
    product_type_terms: Mapping[str, list[str]] = terms.get("product_type_terms", {})  # type: ignore[assignment]
    for ptype, phrases in product_type_terms.items():
        for _phrase, span in _match_term_group(text_lower, phrases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.PRODUCT_TYPE_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=ptype,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.SUPPORTING,
                )
            )

    # -- condition terms ----------------------------------------------------- #
    condition_terms: Mapping[str, list[str]] = terms.get("condition_terms", {})  # type: ignore[assignment]
    for condition, phrases in condition_terms.items():
        for _phrase, span in _match_term_group(text_lower, phrases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.CONDITION_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=condition,
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.QUALIFYING,
                )
            )

    # -- desktop / mobile form terms (as PRODUCT_FORM_TERM hints) ----------- #
    for form_key, term_key in (("desktop", "desktop_terms"), ("mobile", "mobile_terms")):
        form_phrases: list[str] = terms.get(term_key, [])  # type: ignore[assignment]
        for _phrase, span in _match_term_group(text_lower, form_phrases, taken_spans):
            evidence.append(
                _emit(
                    observation=observation,
                    context=context,
                    evidence_type=EvidenceType.PRODUCT_FORM_TERM,
                    raw_value=text[span[0] : span[1]],
                    normalized_value=f"form_factor:{form_key}",
                    source_field="normalized_title",
                    span=span,
                    polarity=EvidencePolarity.QUALIFYING,
                )
            )

    # -- capacity values ------------------------------------------------------ #
    for m in _CAPACITY_RE.finditer(text):
        span = (m.start(), m.end())
        if _overlaps(span, taken_spans):
            continue
        taken_spans.append(span)
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.CAPACITY_VALUE,
                raw_value=m.group(0),
                normalized_value=int(m.group(1)),
                source_field="normalized_title",
                span=span,
                polarity=EvidencePolarity.SUPPORTING,
            )
        )

    # -- MPN-shaped tokens (validated against the catalogue later) ---------- #
    for m in _MPN_RE.finditer(observation.raw_title):
        span = (m.start(), m.end())
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.MPN_TOKEN,
                raw_value=m.group(0),
                normalized_value=m.group(0).upper(),
                source_field="raw_title",
                span=span,
                polarity=EvidencePolarity.UNRESOLVED,
            )
        )

    # -- GTIN-shaped tokens --------------------------------------------------- #
    for m in _GTIN_RE.finditer(observation.raw_title):
        span = (m.start(), m.end())
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.GTIN_TOKEN,
                raw_value=m.group(0),
                normalized_value=m.group(0),
                source_field="raw_title",
                span=span,
                polarity=EvidencePolarity.UNRESOLVED,
            )
        )

    # -- structured attributes (title/attribute contradiction support) ------ #
    for key, value in observation.raw_attributes.items():
        evidence.append(
            _emit(
                observation=observation,
                context=context,
                evidence_type=EvidenceType.STRUCTURED_ATTRIBUTE,
                raw_value=f"{key}={value}",
                normalized_value=str(value),
                source_field=f"raw_attributes.{key}",
                span=None,
                polarity=EvidencePolarity.NEUTRAL,
                confidence=None,
            )
        )

    return tuple(evidence)
