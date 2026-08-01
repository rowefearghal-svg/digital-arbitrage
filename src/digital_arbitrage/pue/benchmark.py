"""GPU release benchmark: dataset schema, loading, and validation (Sprint 3).

This module defines the versioned, labelled benchmark dataset contract used
to evaluate the PUE end-to-end (see
``docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`` and the
Sprint 3 brief). It deliberately extends - rather than replaces - the
Sprint 1 acceptance-fixture case shape
(``tests/fixtures/pue/sprint1_acceptance_v0.1.json`` /
``tests/pue/test_acceptance.py``) so a case can express every field either
fixture format needs; the mandatory acceptance cases and the release
benchmark cases can be loaded and executed through the same code path.

No schema library is used (consistent with the PUE's existing "dataclasses
first" convention - see ADR-024): a dataset is a plain JSON document that is
explicitly, defensively validated field-by-field. Any malformed dataset
raises :class:`~digital_arbitrage.pue.validation.PueValidationError` with a
specific reason - never a bare ``KeyError``/``TypeError``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical_file_hash
from .validation import PueValidationError

#: Schema version of the benchmark *dataset format* itself (this module's
#: contract), independent of the PUE's own ``SCHEMA_VERSION`` and of the
#: dataset's own ``benchmark_version`` (which versions the *content* - see
#: module docstring section 4.1 of the Sprint 3 brief).
BENCHMARK_DATASET_SCHEMA_VERSION = "pue-benchmark-dataset-0.1.0"

#: Default location of the Sprint 3 GPU release benchmark.
DEFAULT_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "pue"
    / "gpu_release_benchmark_v0.1.json"
)

#: Case-tag vocabulary is deliberately open (free-form strings) - tags are
#: descriptive coverage labels (spec section 4.2), not an enum, so a new
#: coverage category never requires a code change here.


# --------------------------------------------------------------------------- #
# Case schema
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One labelled benchmark case (Sprint 3 brief section 4.3).

    Every "expected"/"acceptable" field is optional: a case only asserts
    what its gold annotation actually supports (brief section 4.3's "do not
    force one exact answer"). ``allowed_decision_types`` is the only
    required correctness field, mirroring the Sprint 1 acceptance fixture.
    """

    case_id: str
    title: str | None
    malformed: bool
    structured_attributes: Mapping[str, object] | None

    # --- coverage / provenance metadata (never used for scoring) --------- #
    case_tags: tuple[str, ...]
    difficulty: str | None
    annotation_source: str | None
    annotation_confidence: str
    annotation_notes: str | None
    provenance: str | None

    # --- acceptable outcomes (a case may permit more than one) ----------- #
    allowed_decision_types: tuple[str, ...]
    forbidden_decision_types: tuple[str, ...]
    expected_product_form: str | None
    forbidden_product_forms: tuple[str, ...]
    expected_product_type: str | None
    maximum_justified_identification_level: str | None
    expected_identification_levels: tuple[str, ...]
    expected_comparability: tuple[str, ...]
    expected_identified_brand: str | None
    expected_identified_family: str | None
    expected_identified_model: str | None
    expected_identified_variant: str | None

    # --- Candidate-level gold labels (recall@k, harmful-match control) --- #
    acceptable_catalogue_product_ids: tuple[str, ...]
    forbidden_catalogue_product_ids: tuple[str, ...]
    catalogue_gap: bool
    """True when no acceptable Candidate exists in the tested catalogue
    version at all - Candidate recall must exclude this case rather than
    silently counting it as a retrieval failure (brief section 6.4)."""

    # --- reasoning-trace assertions (beyond the final label) ------------- #
    required_evidence_types: tuple[str, ...]
    forbidden_evidence_types: tuple[str, ...]
    """Evidence types that must NOT appear in the produced Evidence set for
    this case - the only genuine *negative* evidence label in this schema
    (brief section 5 pre-merge correction: without a negative label,
    evidence-precision has no labelled false-positive signal and must be
    reported unavailable rather than fabricated as 1.0)."""
    expected_contradiction_fields: tuple[str, ...]
    require_hard_rejected_candidate: bool
    require_contradicted_claim: bool
    require_multiple_hypotheses: bool
    min_evidence_count: int

    # --- abstention semantics --------------------------------------------- #
    acceptable_abstention_reasons: tuple[str, ...]
    abstention_classification: str | None
    """Explicit gold classification of an ABSTAINED outcome on this case -
    one of ``"justified"`` or ``"avoidable"``, or ``None`` when this case's
    abstention behaviour has not been independently hand-adjudicated at
    all (Sprint 3 final release-integrity correction item 7).

    Deliberately **not** inferred as ``justified = abstained and not
    avoidable`` from a single boolean: that inference silently treated
    every abstention nobody had explicitly marked ``avoidable`` as
    ``justified`` by default, which meant the
    ``every_abstention_classified_justified_or_avoidable`` release gate
    could never actually catch a genuinely unlabelled abstention (every
    case was, in effect, always pre-classified). A ``None`` here must
    cause that gate check to fail for any case that actually abstains -
    an unlabelled abstention is a gap in the gold annotation, not a
    default "fine"."""

    # --- harm / domain classification ------------------------------------ #
    forbidden_harmful_outcomes: tuple[str, ...]
    """Any of ``"accessory_to_complete_product"``,
    ``"packaging_to_complete_product"``, ``"harmful_false_match"`` - see
    :data:`HARMFUL_OUTCOME_KINDS`."""
    unsupported_domain: bool
    """True when this listing is gold-labelled as outside the GPU domain
    (must not be scored as an ordinary identification error)."""

    # --- explicit search/comparison context (Sprint 3 final correction
    # item 2) --------------------------------------------------------------
    search_query: str | None
    """The buyer search query this listing is being evaluated *against*
    for classifier/PUE differential and comparability-reporting purposes
    only - e.g. ``"RTX 4090"`` for a listing titled "EK Quantum RTX 4090
    water block". Deliberately never derived from ``title`` (a listing's
    own title is not a buyer's search intent - matching a listing against
    a search query built from its own title is tautological and can never
    reveal a real product-form mismatch between what was searched for and
    what was found). ``None`` means this case has no comparison context at
    all: the existing title classifier is not run and no
    ``ClassifierPueComparison`` is produced for it (excluded from every
    classifier/differential metric, never silently compared against an
    implicit or synthesized query)."""
    searched_product_form: str | None
    """Gold annotation of what product form the ``search_query`` searcher
    was realistically looking for (almost always ``"complete_product"`` -
    a buyer searching a bare GPU family name is looking for a graphics
    card, not an accessory) - descriptive context only, never fed into PUE
    factual identity reasoning."""
    searched_family: str | None
    """Gold annotation of the GPU family the ``search_query`` denotes
    (e.g. ``"rtx 4090"``) - descriptive context only, never fed into PUE
    factual identity reasoning."""

    def outcome_options(self) -> int:
        """How many materially different acceptable outcomes this case
        permits (brief section 4.3: "a case may define multiple acceptable
        outcomes")."""
        return max(1, len(self.allowed_decision_types))


#: Recognized harmful-outcome kinds (brief sections 6.1 / 7 / 8).
HARMFUL_OUTCOME_KINDS = frozenset(
    {"accessory_to_complete_product", "packaging_to_complete_product", "harmful_false_match"}
)

_VALID_CONFIDENCE = frozenset({"low", "medium", "high"})


def _as_str_tuple(value: object, *, field_name: str, case_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise PueValidationError(f"case {case_id!r}: {field_name} must be a list of strings")
    return tuple(str(v) for v in value)


def _as_optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _as_bool(value: object, *, field_name: str, case_id: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise PueValidationError(f"case {case_id!r}: {field_name} must be a boolean")
    return value


def _case_from_dict(entry: Mapping[str, object]) -> BenchmarkCase:
    if not isinstance(entry, Mapping):
        raise PueValidationError(f"benchmark case must be an object, got {type(entry).__name__}")
    case_id = entry.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise PueValidationError(f"benchmark case missing a non-empty 'case_id': {entry!r}")

    malformed = _as_bool(entry.get("malformed"), field_name="malformed", case_id=case_id)
    title = entry.get("title")
    if not malformed:
        # An empty string is a deliberately valid (if degenerate) title -
        # e.g. an "empty title" edge case distinct from a malformed,
        # non-string input; only a missing/non-string title is rejected.
        if not isinstance(title, str):
            raise PueValidationError(f"case {case_id!r}: 'title' must be a string")
    elif title is not None and not isinstance(title, str):
        raise PueValidationError(f"case {case_id!r}: 'title' must be a string or null")

    allowed = _as_str_tuple(
        entry.get("allowed_decision_types"), field_name="allowed_decision_types", case_id=case_id
    )
    if not allowed:
        raise PueValidationError(
            f"case {case_id!r}: 'allowed_decision_types' must be a non-empty list"
        )

    confidence = str(entry.get("annotation_confidence", "medium"))
    if confidence not in _VALID_CONFIDENCE:
        raise PueValidationError(
            f"case {case_id!r}: annotation_confidence must be one of {sorted(_VALID_CONFIDENCE)}, "
            f"got {confidence!r}"
        )

    harmful = _as_str_tuple(
        entry.get("forbidden_harmful_outcomes"),
        field_name="forbidden_harmful_outcomes",
        case_id=case_id,
    )
    unknown_harmful = set(harmful) - HARMFUL_OUTCOME_KINDS
    if unknown_harmful:
        raise PueValidationError(
            f"case {case_id!r}: unknown forbidden_harmful_outcomes {sorted(unknown_harmful)}; "
            f"must be a subset of {sorted(HARMFUL_OUTCOME_KINDS)}"
        )

    structured = entry.get("structured_attributes")
    if structured is not None and not isinstance(structured, Mapping):
        raise PueValidationError(f"case {case_id!r}: 'structured_attributes' must be an object")

    min_evidence = entry.get("min_evidence_count", 0)
    if not isinstance(min_evidence, int) or isinstance(min_evidence, bool) or min_evidence < 0:
        raise PueValidationError(
            f"case {case_id!r}: 'min_evidence_count' must be a non-negative int"
        )

    catalogue_gap = _as_bool(
        entry.get("catalogue_gap"), field_name="catalogue_gap", case_id=case_id
    )
    acceptable_ids = _as_str_tuple(
        entry.get("acceptable_catalogue_product_ids"),
        field_name="acceptable_catalogue_product_ids",
        case_id=case_id,
    )
    if catalogue_gap and acceptable_ids:
        raise PueValidationError(
            f"case {case_id!r}: catalogue_gap=true is incompatible with a non-empty "
            "acceptable_catalogue_product_ids (a catalogue gap means no acceptable "
            "Candidate exists at all)"
        )

    abstention_classification = _as_optional_str(entry.get("abstention_classification"))
    _VALID_ABSTENTION_CLASSIFICATIONS = frozenset({"justified", "avoidable"})
    if (
        abstention_classification is not None
        and abstention_classification not in _VALID_ABSTENTION_CLASSIFICATIONS
    ):
        raise PueValidationError(
            f"case {case_id!r}: abstention_classification must be one of "
            f"{sorted(_VALID_ABSTENTION_CLASSIFICATIONS)} or omitted, got "
            f"{abstention_classification!r}"
        )
    if abstention_classification is not None and "abstained" not in allowed:
        # An explicit abstention classification only means something for a
        # case that permits ABSTAINED as one of its acceptable outcomes at
        # all; otherwise it can never be evaluated against anything.
        raise PueValidationError(
            f"case {case_id!r}: abstention_classification={abstention_classification!r} "
            "requires 'abstained' to be present in allowed_decision_types"
        )

    return BenchmarkCase(
        case_id=case_id,
        title=title,
        malformed=malformed,
        structured_attributes=dict(structured) if structured is not None else None,
        case_tags=_as_str_tuple(entry.get("case_tags"), field_name="case_tags", case_id=case_id),
        difficulty=_as_optional_str(entry.get("difficulty")),
        annotation_source=_as_optional_str(entry.get("annotation_source")),
        annotation_confidence=confidence,
        annotation_notes=_as_optional_str(entry.get("annotation_notes")),
        provenance=_as_optional_str(entry.get("provenance")),
        allowed_decision_types=allowed,
        forbidden_decision_types=_as_str_tuple(
            entry.get("forbidden_decision_types"),
            field_name="forbidden_decision_types",
            case_id=case_id,
        ),
        expected_product_form=_as_optional_str(entry.get("expected_product_form")),
        forbidden_product_forms=_as_str_tuple(
            entry.get("forbidden_product_forms"),
            field_name="forbidden_product_forms",
            case_id=case_id,
        ),
        expected_product_type=_as_optional_str(entry.get("expected_product_type")),
        maximum_justified_identification_level=_as_optional_str(
            entry.get("maximum_justified_identification_level")
        ),
        expected_identification_levels=_as_str_tuple(
            entry.get("expected_identification_levels"),
            field_name="expected_identification_levels",
            case_id=case_id,
        ),
        expected_comparability=_as_str_tuple(
            entry.get("expected_comparability"),
            field_name="expected_comparability",
            case_id=case_id,
        ),
        expected_identified_brand=_as_optional_str(entry.get("expected_identified_brand")),
        expected_identified_family=_as_optional_str(entry.get("expected_identified_family")),
        expected_identified_model=_as_optional_str(entry.get("expected_identified_model")),
        expected_identified_variant=_as_optional_str(entry.get("expected_identified_variant")),
        acceptable_catalogue_product_ids=acceptable_ids,
        forbidden_catalogue_product_ids=_as_str_tuple(
            entry.get("forbidden_catalogue_product_ids"),
            field_name="forbidden_catalogue_product_ids",
            case_id=case_id,
        ),
        catalogue_gap=catalogue_gap,
        required_evidence_types=_as_str_tuple(
            entry.get("required_evidence_types"),
            field_name="required_evidence_types",
            case_id=case_id,
        ),
        forbidden_evidence_types=_as_str_tuple(
            entry.get("forbidden_evidence_types"),
            field_name="forbidden_evidence_types",
            case_id=case_id,
        ),
        expected_contradiction_fields=_as_str_tuple(
            entry.get("expected_contradiction_fields"),
            field_name="expected_contradiction_fields",
            case_id=case_id,
        ),
        require_hard_rejected_candidate=_as_bool(
            entry.get("require_hard_rejected_candidate"),
            field_name="require_hard_rejected_candidate",
            case_id=case_id,
        ),
        require_contradicted_claim=_as_bool(
            entry.get("require_contradicted_claim"),
            field_name="require_contradicted_claim",
            case_id=case_id,
        ),
        require_multiple_hypotheses=_as_bool(
            entry.get("require_multiple_hypotheses"),
            field_name="require_multiple_hypotheses",
            case_id=case_id,
        ),
        min_evidence_count=min_evidence,
        acceptable_abstention_reasons=_as_str_tuple(
            entry.get("acceptable_abstention_reasons"),
            field_name="acceptable_abstention_reasons",
            case_id=case_id,
        ),
        abstention_classification=abstention_classification,
        forbidden_harmful_outcomes=harmful,
        unsupported_domain=_as_bool(
            entry.get("unsupported_domain"), field_name="unsupported_domain", case_id=case_id
        ),
        search_query=_as_optional_str(entry.get("search_query")),
        searched_product_form=_as_optional_str(entry.get("searched_product_form")),
        searched_family=_as_optional_str(entry.get("searched_family")),
    )


# --------------------------------------------------------------------------- #
# Dataset schema
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    """A complete, validated benchmark dataset (Sprint 3 brief section 4.1)."""

    dataset_id: str
    dataset_schema_version: str
    benchmark_version: str
    created_date: str
    curator: str
    domain: str
    knowledge_version: str
    policy_version: str
    provenance_note: str
    cases: tuple[BenchmarkCase, ...]
    corrections: tuple[Mapping[str, object], ...] = field(default_factory=tuple)

    def case_by_id(self, case_id: str) -> BenchmarkCase | None:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        return None


_REQUIRED_DATASET_FIELDS = (
    "dataset_id",
    "benchmark_version",
    "created_date",
    "curator",
    "domain",
    "knowledge_version",
    "policy_version",
    "provenance_note",
    "cases",
)


def dataset_file_hash(path: Path | str = DEFAULT_BENCHMARK_PATH) -> str:
    """Stable, cross-platform SHA-256 hash of the dataset's *canonical JSON
    content* (see :mod:`digital_arbitrage.pue.canonical`) - not the raw file
    bytes, which would vary with CRLF/LF line-ending conversion, incidental
    whitespace, or key ordering even for byte-different files that encode
    the exact same dataset.

    Recorded in release reports/manifests (brief section 4.1 "stable file
    hash in the resulting release report") so a release is bound to the
    exact *content* of the dataset that produced it - not merely its
    declared version string, and not an artefact of the checkout's line
    endings.
    """
    return canonical_file_hash(path)


def load_benchmark_dataset(path: Path | str = DEFAULT_BENCHMARK_PATH) -> BenchmarkDataset:
    """Load and validate a benchmark dataset JSON file.

    Raises :class:`PueValidationError` for: unreadable/non-JSON files,
    missing required dataset-level metadata, an unsupported
    ``dataset_schema_version``, a missing/empty ``cases`` list, a duplicate
    ``case_id``, or any malformed case (see :func:`_case_from_dict`).
    """
    resolved = Path(path)
    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise PueValidationError(f"could not read benchmark dataset {resolved}: {exc}") from exc
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PueValidationError(f"benchmark dataset {resolved} is not valid JSON: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise PueValidationError(f"benchmark dataset {resolved} must be a JSON object")

    declared_schema = raw.get("dataset_schema_version", BENCHMARK_DATASET_SCHEMA_VERSION)
    if declared_schema != BENCHMARK_DATASET_SCHEMA_VERSION:
        raise PueValidationError(
            f"benchmark dataset {resolved} declares unsupported "
            f"dataset_schema_version {declared_schema!r}; this loader supports only "
            f"{BENCHMARK_DATASET_SCHEMA_VERSION!r}"
        )

    missing = [f for f in _REQUIRED_DATASET_FIELDS if f not in raw]
    if missing:
        raise PueValidationError(
            f"benchmark dataset {resolved} is missing required field(s): {missing}"
        )

    cases_raw = raw["cases"]
    if not isinstance(cases_raw, list) or not cases_raw:
        raise PueValidationError(f"benchmark dataset {resolved}: 'cases' must be a non-empty list")

    cases = tuple(_case_from_dict(entry) for entry in cases_raw)

    seen_ids: set[str] = set()
    for case in cases:
        if case.case_id in seen_ids:
            raise PueValidationError(
                f"benchmark dataset {resolved}: duplicate case_id {case.case_id!r}"
            )
        seen_ids.add(case.case_id)

    corrections_raw = raw.get("corrections", [])
    if not isinstance(corrections_raw, list):
        raise PueValidationError(f"benchmark dataset {resolved}: 'corrections' must be a list")
    for correction in corrections_raw:
        if not isinstance(correction, Mapping):
            raise PueValidationError(
                f"benchmark dataset {resolved}: each 'corrections' entry must be an object"
            )
        required_correction_fields = (
            "case_id",
            "prior_label",
            "corrected_label",
            "adjudication_reason",
            "evidence",
            "benchmark_version_change",
        )
        missing_correction = [f for f in required_correction_fields if f not in correction]
        if missing_correction:
            raise PueValidationError(
                f"benchmark dataset {resolved}: a correction entry is missing required "
                f"field(s) {missing_correction} (brief section 4.4 label-integrity rule)"
            )

    return BenchmarkDataset(
        dataset_id=str(raw["dataset_id"]),
        dataset_schema_version=str(declared_schema),
        benchmark_version=str(raw["benchmark_version"]),
        created_date=str(raw["created_date"]),
        curator=str(raw["curator"]),
        domain=str(raw["domain"]),
        knowledge_version=str(raw["knowledge_version"]),
        policy_version=str(raw["policy_version"]),
        provenance_note=str(raw["provenance_note"]),
        cases=cases,
        corrections=tuple(dict(c) for c in corrections_raw),
    )


def validate_dataset_file(path: Path | str = DEFAULT_BENCHMARK_PATH) -> BenchmarkDataset:
    """Alias for :func:`load_benchmark_dataset` - validation *is* loading
    here (there is no separate parse step that can succeed independently),
    kept as a distinct public name for CLI/test readability."""
    return load_benchmark_dataset(path)


def case_coverage_by_tag(cases: Sequence[BenchmarkCase]) -> dict[str, int]:
    """Count of cases carrying each ``case_tags`` value (dataset coverage
    summary; brief section 21 final-report requirement)."""
    counts: dict[str, int] = {}
    for case in cases:
        for tag in case.case_tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts
