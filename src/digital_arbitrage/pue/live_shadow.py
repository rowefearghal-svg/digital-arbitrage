"""PUE v0.1 post-release live shadow trial.

Uses the existing live providers, normalizer, title classifier and PUE shadow
execution. No commercial behaviour is changed: the command does not publish PUE
results into the scoring path and does not modify recommendations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..classification.classifier import ListingClassifier, build_search_profile
from ..normalization import Normalizer
from ..pipeline.pue_shadow import PueShadowCaseResult, ShadowConfig, run_pue_shadow
from ..product_scanner.models import Listing
from ..product_scanner.scanner import Scanner
from ..providers.live import build_live_provider_from_env
from ..providers.live.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from ..pue.comparison import ClassifierPueComparison
from ..pue.enums import ComparabilityStatus, DecisionType, IdentificationLevel, ProductForm
from ..pue.policies import DecisionPolicy

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("var/pue/live-shadow")
DEFAULT_MAX_RESULTS = 25
PUE_RELEASE_MANIFEST_PATH = Path("data/pue/releases/pue-v0.1.0.json")
TRIAL_SCHEMA_VERSION = "pue-live-shadow-0.1.0"
CLASSIFIER_VERSION = "title-classifier-1.0"

FAILURE_CATEGORIES: dict[type[ProviderError], str] = {
    ProviderAuthError: "PROVIDER_AUTHENTICATION_FAILURE",
    ProviderConfigError: "PROVIDER_AUTHENTICATION_FAILURE",
    ProviderRateLimitError: "PROVIDER_RATE_LIMIT",
    ProviderResponseError: "PROVIDER_RESPONSE_FAILURE",
    ProviderError: "PROVIDER_NETWORK_FAILURE",
}


class LiveShadowError(Exception):
    """Raised for manifest or trial setup problems."""


@dataclass(frozen=True, slots=True)
class QueryEntry:
    """One query from the live shadow manifest."""

    query_id: str
    search_text: str
    searched_product_form: str
    searched_product_type: str
    searched_brand: str | None
    searched_family: str | None
    searched_model: str | None
    max_results_per_provider: int
    providers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "search_text": self.search_text,
            "searched_product_form": self.searched_product_form,
            "searched_product_type": self.searched_product_type,
            "searched_brand": self.searched_brand,
            "searched_family": self.searched_family,
            "searched_model": self.searched_model,
            "max_results_per_provider": self.max_results_per_provider,
            "providers": list(self.providers),
        }


@dataclass(frozen=True, slots=True)
class QueryManifest:
    """Versioned query manifest."""

    manifest_id: str
    version: str
    description: str
    queries: tuple[QueryEntry, ...]

    def query_by_id(self, query_id: str) -> QueryEntry | None:
        for query in self.queries:
            if query.query_id == query_id:
                return query
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "version": self.version,
            "description": self.description,
            "queries": [q.to_dict() for q in self.queries],
        }


@dataclass(slots=True)
class ProviderOutcome:
    """Results and diagnostics for a single (query, provider) execution."""

    query_id: str
    provider: str
    requested: int
    returned: int = 0
    normalized: int = 0
    pue_cases: int = 0
    error: str | None = None
    error_category: str | None = None
    latency_seconds: float = 0.0
    case_results: list[PueShadowCaseResult] = field(default_factory=list)


@dataclass(slots=True)
class TrialResult:
    """Summary of a complete (or partial) live shadow trial."""

    run_id: str
    status: str
    start_time: str
    end_time: str
    manifest_id: str
    manifest_hash: str
    providers_requested: tuple[str, ...]
    providers_contacted: tuple[str, ...]
    pue_release_manifest_hash: str
    classifier_version: str
    result_schema_version: str
    pue_db_path: str
    output_paths: dict[str, str]
    outcomes: list[ProviderOutcome]
    known_limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "manifest_id": self.manifest_id,
            "manifest_hash": self.manifest_hash,
            "providers_requested": list(self.providers_requested),
            "providers_contacted": list(self.providers_contacted),
            "pue_release_manifest_hash": self.pue_release_manifest_hash,
            "classifier_version": self.classifier_version,
            "result_schema_version": self.result_schema_version,
            "pue_db_path": self.pue_db_path,
            "output_paths": self.output_paths,
            "known_limitations": self.known_limitations,
        }


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _manifest_hash(manifest: QueryManifest) -> str:
    payload = manifest.to_dict()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_manifest(raw: dict[str, Any]) -> None:
    if "manifest_id" not in raw:
        raise LiveShadowError("manifest missing 'manifest_id'")
    if "version" not in raw:
        raise LiveShadowError("manifest missing 'version'")
    if "queries" not in raw or not isinstance(raw["queries"], list):
        raise LiveShadowError("manifest missing 'queries' list")
    seen_ids: set[str] = set()
    for i, q in enumerate(raw["queries"]):
        qid = q.get("query_id")
        if not qid:
            raise LiveShadowError(f"query {i} missing 'query_id'")
        if qid in seen_ids:
            raise LiveShadowError(f"duplicate query_id: {qid}")
        seen_ids.add(qid)
        if "search_text" not in q:
            raise LiveShadowError(f"query {qid} missing 'search_text'")
        if "providers" not in q or not isinstance(q["providers"], list):
            raise LiveShadowError(f"query {qid} missing 'providers' list")


def load_query_manifest(path: str | Path) -> QueryManifest:
    """Load and lightly validate a query manifest."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_manifest(raw)
    queries = tuple(
        QueryEntry(
            query_id=str(q["query_id"]),
            search_text=str(q["search_text"]),
            searched_product_form=str(q.get("searched_product_form", "complete_product")),
            searched_product_type=str(q.get("searched_product_type", "graphics card")),
            searched_brand=q.get("searched_brand"),
            searched_family=q.get("searched_family"),
            searched_model=q.get("searched_model"),
            max_results_per_provider=int(q.get("max_results_per_provider", DEFAULT_MAX_RESULTS)),
            providers=tuple(str(p) for p in q["providers"]),
        )
        for q in raw["queries"]
    )
    return QueryManifest(
        manifest_id=str(raw["manifest_id"]),
        version=str(raw["version"]),
        description=str(raw.get("description", "")),
        queries=queries,
    )


def _error_category(exc: Exception) -> str:
    for cls, name in FAILURE_CATEGORIES.items():
        if isinstance(exc, cls):
            return name
    return "PROVIDER_NETWORK_FAILURE"


def _build_provider_scanner(
    provider_name: str, limit: int, env: Mapping[str, str] | None
) -> Scanner:
    # Build the single live provider explicitly so scanner use is traceable.
    provider = build_live_provider_from_env(provider_name, {}, env=env)
    return Scanner([provider], max_results_per_provider=limit)


def _acquire_and_process(
    query: QueryEntry,
    provider_name: str,
    limit: int,
    db_path: Path,
    env: Mapping[str, str] | None,
) -> ProviderOutcome:
    outcome = ProviderOutcome(query_id=query.query_id, provider=provider_name, requested=limit)
    start = time.monotonic()
    listings: list[Listing] = []
    try:
        scanner = _build_provider_scanner(provider_name, limit, env)
        provider = scanner.providers[0]
        listings = provider.search(query.search_text, limit=limit)
    except Exception as exc:  # noqa: BLE001 - isolate provider failures per spec
        outcome.error = str(exc)
        outcome.error_category = _error_category(exc)
        logger.warning("provider %r failed for query %r: %s", provider_name, query.query_id, exc)
        outcome.latency_seconds = round(time.monotonic() - start, 3)
        return outcome

    outcome.returned = len(listings)
    outcome.latency_seconds = round(time.monotonic() - start, 3)

    if not listings:
        return outcome

    normalizer = Normalizer()
    normalized = normalizer.normalize_many(listings)
    outcome.normalized = len(normalized)

    search_profile = build_search_profile(query.search_text)
    classifier = ListingClassifier()
    classifier.classify_many(normalized, search_profile)

    shadow_config = ShadowConfig(
        enabled=True,
        db_path=db_path,
        policy=DecisionPolicy(),
    )
    case_results = list(
        run_pue_shadow(normalized, config=shadow_config, search_profile=search_profile)
    )
    outcome.pue_cases = len(case_results)
    outcome.case_results = case_results
    return outcome


def _unique_providers(outcomes: Sequence[ProviderOutcome]) -> list[str]:
    return sorted({o.provider for o in outcomes if not o.error})


def _aggregate_status(outcomes: Sequence[ProviderOutcome]) -> str:
    if not outcomes:
        return "FAILURE"
    if all(o.error for o in outcomes):
        return "FAILURE"
    if any(o.error for o in outcomes):
        return "PARTIAL_SUCCESS"
    return "SUCCESS"


def _pue_distribution(outcomes: Sequence[ProviderOutcome]) -> dict[str, Any]:
    decision_counts: dict[str, int] = {}
    product_form_counts: dict[str, int] = {}
    identification_counts: dict[str, int] = {}
    comparability_counts: dict[str, int] = {}
    abstention_counts: dict[str, int] = {}
    comparison_categories: dict[str, int] = {}
    zero_candidate = 0
    pue_failures = 0
    latencies: list[float] = []

    for outcome in outcomes:
        for case in outcome.case_results:
            record = case.reasoning_record
            decision = record.decision
            result = case.result
            decision_counts[decision.decision_type.value] = (
                decision_counts.get(decision.decision_type.value, 0) + 1
            )
            product_form_counts[decision.product_form.value] = (
                product_form_counts.get(decision.product_form.value, 0) + 1
            )
            identification_counts[decision.identification_level.value] = (
                identification_counts.get(decision.identification_level.value, 0) + 1
            )
            comparability_counts[result.comparability_status.value] = (
                comparability_counts.get(result.comparability_status.value, 0) + 1
            )
            if decision.abstention_reason:
                abstention_counts[decision.abstention_reason.value] = (
                    abstention_counts.get(decision.abstention_reason.value, 0) + 1
                )
            if not result.catalogue_product_id and not decision.abstention_reason:
                zero_candidate += 1
            if decision.decision_type == DecisionType.PROCESSING_FAILED:
                pue_failures += 1
            if case.comparison:
                key = _classifier_pue_category(case.comparison)
                comparison_categories[key] = comparison_categories.get(key, 0) + 1
            total_ms = record.operational_metrics.get("total_ms", 0.0)
            latencies.append(cast(float, total_ms) / 1000.0)

    if latencies:
        latencies.sort()
        median = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
    else:
        median = 0.0
        p95 = 0.0

    return {
        "by_provider": _distribution_by_provider(outcomes),
        "aggregate": {
            "decision_counts": decision_counts,
            "product_form_counts": product_form_counts,
            "identification_level_counts": identification_counts,
            "comparability_counts": comparability_counts,
            "abstention_reason_counts": abstention_counts,
            "classifier_pue_comparison_categories": comparison_categories,
            "zero_candidate_count": zero_candidate,
            "pue_processing_failures": pue_failures,
            "median_latency_seconds": round(median, 3),
            "p95_latency_seconds": round(p95, 3),
            "total_cases": sum(1 for o in outcomes for _ in o.case_results),
        },
    }


def _distribution_by_provider(outcomes: Sequence[ProviderOutcome]) -> dict[str, Any]:
    by_provider: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        by_provider.setdefault(outcome.provider, {"cases": 0, "decisions": {}, "product_forms": {}})
        for case in outcome.case_results:
            by_provider[outcome.provider]["cases"] += 1
            d = case.reasoning_record.decision.decision_type.value
            by_provider[outcome.provider]["decisions"][d] = (
                by_provider[outcome.provider]["decisions"].get(d, 0) + 1
            )
            p = case.reasoning_record.decision.product_form.value
            by_provider[outcome.provider]["product_forms"][p] = (
                by_provider[outcome.provider]["product_forms"].get(p, 0) + 1
            )
    return by_provider


def _classifier_pue_category(comparison: ClassifierPueComparison) -> str:
    if comparison.category:
        return comparison.category.value
    return "OTHER_DISAGREEMENT"


def _acquisition_report(outcomes: Sequence[ProviderOutcome]) -> dict[str, Any]:
    return {
        "by_provider_and_query": [
            {
                "query_id": o.query_id,
                "provider": o.provider,
                "requested": o.requested,
                "returned": o.returned,
                "normalized": o.normalized,
                "pue_cases": o.pue_cases,
                "error": o.error,
                "error_category": o.error_category,
                "latency_seconds": o.latency_seconds,
            }
            for o in outcomes
        ],
        "totals": {
            "total_requested": sum(o.requested for o in outcomes),
            "total_returned": sum(o.returned for o in outcomes),
            "total_normalized": sum(o.normalized for o in outcomes),
            "total_pue_cases": sum(o.pue_cases for o in outcomes),
            "failed_provider_queries": [
                {
                    "query_id": o.query_id,
                    "provider": o.provider,
                    "error_category": o.error_category,
                    "error": o.error,
                }
                for o in outcomes
                if o.error
            ],
        },
    }


def _review_priority(case: PueShadowCaseResult, query: QueryEntry) -> tuple[int, str]:
    decision = case.reasoning_record.decision
    result = case.result
    comparison = case.comparison
    title = case.reasoning_record.observation.normalized_title.lower()

    if comparison and comparison.category == "product_form_disagreement":
        return 1, "product_form_disagreement"
    if comparison and comparison.category == "pue_blocked_direct_comparability":
        return 2, "pue_blocked_direct_comparability"
    if decision.product_form == ProductForm.COMPLETE_PRODUCT and any(
        term in title
        for term in ("compatible", "compatibility", "cable", "adapter", "box", "sticker")
    ):
        return 3, "complete_product_with_non_complete_language"
    if decision.product_form == ProductForm.COMPLETE_PRODUCT and decision.identification_level in (
        IdentificationLevel.FAMILY,
        IdentificationLevel.BRAND_AND_PRODUCT_TYPE,
        IdentificationLevel.PRODUCT_TYPE,
        IdentificationLevel.UNKNOWN,
    ):
        return 4, "complete_product_weak_identification"
    if decision.identification_level in (
        IdentificationLevel.FAMILY,
        IdentificationLevel.BRAND_AND_PRODUCT_TYPE,
        IdentificationLevel.PRODUCT_TYPE,
        IdentificationLevel.UNKNOWN,
    ):
        return 5, "weak_identification"
    if decision.abstention_reason:
        return 6, f"abstention:{decision.abstention_reason.value}"
    if result.comparability_status == ComparabilityStatus.NOT_ASSESSED:
        return 7, "unknown_comparability"
    if not result.catalogue_product_id:
        return 8, "zero_candidate"
    return 9, "representative_agreement"


def _build_review_queue(
    outcomes: Sequence[ProviderOutcome], manifest: QueryManifest
) -> list[dict[str, Any]]:
    queue: list[tuple[tuple[int, str], dict[str, Any]]] = []
    for outcome in outcomes:
        query = manifest.query_by_id(outcome.query_id)
        for case in outcome.case_results:
            fallback = QueryEntry(outcome.query_id, "", "", "", None, None, None, 0, ())
            rank, reason = _review_priority(case, query or fallback)
            record = case.reasoning_record
            obs = record.observation
            result = case.result
            item: dict[str, Any] = {
                "priority_rank": rank,
                "review_reason": reason,
                "provider": obs.provider,
                "provider_listing_id": obs.provider_listing_id,
                "query_id": outcome.query_id,
                "search_text": query.search_text if query else "",
                "raw_title": obs.raw_title,
                "normalized_title": obs.normalized_title,
                "classifier_label": (case.comparison.classifier_label if case.comparison else None),
                "pue_decision_type": record.decision.decision_type.value,
                "pue_product_form": record.decision.product_form.value,
                "pue_identification_level": record.decision.identification_level.value,
                "pue_comparability_status": result.comparability_status.value,
                "selected_catalogue_product_id": result.catalogue_product_id,
                "explanation_summary": result.explanation_summary,
                "review_fields": {
                    "review_status": "pending",
                    "reviewed_product_form": None,
                    "reviewed_identification_level": None,
                    "reviewed_comparability": None,
                    "harmful_error": None,
                    "review_notes": "",
                },
            }
            queue.append(((rank, reason), item))
    queue.sort(key=lambda x: x[0])
    return [item for _, item in queue]


def _render_markdown_review_queue(queue: list[dict[str, Any]]) -> str:
    lines = [
        "# PUE v0.1 Live Shadow Trial — Manual Review Queue",
        "",
        f"Queued cases: {len(queue)}",
        "",
        "| Rank | Reason | Provider | Listing ID | Raw Title | PUE Decision | Product Form |",
        "|------|--------|----------|------------|-----------|--------------|--------------|",
    ]
    for item in queue:
        lines.append(
            f"| {item['priority_rank']} | {item['review_reason']} | "
            f"{item['provider']} | {item['provider_listing_id']} | "
            f"{item['raw_title'][:80]} | {item['pue_decision_type']} | "
            f"{item['pue_product_form']} |"
        )
    lines.append("")
    lines.append("Full review data is available in `review_queue.json`.")
    return "\n".join(lines)


def _render_markdown_run_report(result: TrialResult, distribution: dict[str, Any]) -> str:
    lines = [
        f"# PUE v0.1 Live Shadow Trial Report — {result.run_id}",
        "",
        f"- **Status:** {result.status}",
        f"- **Start:** {result.start_time}",
        f"- **End:** {result.end_time}",
        f"- **Manifest:** {result.manifest_id} ({result.manifest_hash})",
        f"- **Providers requested:** {', '.join(result.providers_requested)}",
        f"- **Providers contacted:** {', '.join(result.providers_contacted)}",
        f"- **PUE release manifest hash:** {result.pue_release_manifest_hash}",
        "",
        "## Acquisition summary",
        "",
    ]
    return "\n".join(lines)  # Minimal report; full data is in JSON.


def _write_reports(
    output_dir: Path,
    result: TrialResult,
    distribution: dict[str, Any],
    acquisition: dict[str, Any],
    queue: list[dict[str, Any]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    run_manifest_path = output_dir / f"{result.run_id}_run_manifest.json"
    run_manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    paths["run_manifest"] = str(run_manifest_path)

    acquisition_path = output_dir / f"{result.run_id}_acquisition_report.json"
    acquisition_path.write_text(json.dumps(acquisition, indent=2), encoding="utf-8")
    paths["acquisition_report"] = str(acquisition_path)

    distribution_path = output_dir / f"{result.run_id}_pue_distribution.json"
    distribution_path.write_text(json.dumps(distribution, indent=2), encoding="utf-8")
    paths["pue_distribution"] = str(distribution_path)

    queue_path = output_dir / f"{result.run_id}_review_queue.json"
    queue_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    paths["review_queue_json"] = str(queue_path)

    queue_md_path = output_dir / f"{result.run_id}_review_queue.md"
    queue_md_path.write_text(_render_markdown_review_queue(queue), encoding="utf-8")
    paths["review_queue_markdown"] = str(queue_md_path)

    run_md_path = output_dir / f"{result.run_id}_run_report.md"
    run_md_path.write_text(_render_markdown_run_report(result, distribution), encoding="utf-8")
    paths["run_report_markdown"] = str(run_md_path)

    return paths


def run_live_shadow_trial(
    manifest_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    max_results_per_query: int | None = None,
    provider_filter: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    known_limitations: list[str] | None = None,
) -> TrialResult:
    """Run the live shadow trial described by ``manifest_path``.

    Returns a :class:`TrialResult`; on success or partial success, reports are
    written to ``output_dir``. Provider failures are isolated and recorded, never
    raised.
    """
    manifest = load_query_manifest(manifest_path)
    out = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex[:16]
    db_path = out / f"{run_id}_pue_shadow.db"
    start = _now()

    pue_manifest_hash = _file_sha256(PUE_RELEASE_MANIFEST_PATH)
    outcomes: list[ProviderOutcome] = []

    requested_providers: set[str] = set()
    for query in manifest.queries:
        for provider_name in query.providers:
            requested_providers.add(provider_name)
    requested_providers = requested_providers | set(provider_filter or ())

    for query in manifest.queries:
        for provider_name in query.providers:
            if provider_filter and provider_name not in provider_filter:
                continue
            limit = max_results_per_query or query.max_results_per_provider
            outcome = _acquire_and_process(query, provider_name, limit, db_path, env)
            outcomes.append(outcome)

    end = _now()
    status = _aggregate_status(outcomes)
    contacted = _unique_providers(outcomes)

    distribution = _pue_distribution(outcomes)
    acquisition = _acquisition_report(outcomes)
    queue = _build_review_queue(outcomes, manifest)

    result = TrialResult(
        run_id=run_id,
        status=status,
        start_time=start.isoformat(),
        end_time=end.isoformat(),
        manifest_id=manifest.manifest_id,
        manifest_hash=_manifest_hash(manifest),
        providers_requested=tuple(sorted(requested_providers)),
        providers_contacted=tuple(contacted),
        pue_release_manifest_hash=pue_manifest_hash,
        classifier_version=CLASSIFIER_VERSION,
        result_schema_version=TRIAL_SCHEMA_VERSION,
        pue_db_path=str(db_path),
        output_paths={},
        outcomes=outcomes,
        known_limitations=known_limitations or [],
    )
    result.output_paths = _write_reports(out, result, distribution, acquisition, queue)
    return result
