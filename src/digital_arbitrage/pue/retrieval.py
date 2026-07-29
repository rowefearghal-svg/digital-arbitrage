"""Candidate Retrieval (spec section 14).

Retrieval is staged: exact identifiers, structured filtering, normalized
token overlap, then RapidFuzz reranking. The retrieval score ranks
Candidates only; it never publishes identity by itself (spec 14.2).

Note on the component contract: the spec's abstract signature is
``retrieve_candidates(hypotheses, repository, context) -> tuple[Candidate, ...]``.
Because exact-identifier retrieval needs the raw MPN/GTIN Claims and
normalized-token/fuzzy retrieval needs the Observation's title text (neither
of which is a field on ``ProductHypothesis``), this implementation adds two
required keyword-only parameters (``observation`` and ``claims``). This is a
documented, minimal deviation from the literal spec signature; the staged
retrieval behavior itself follows the spec exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from rapidfuzz import fuzz

from ..normalization.text import tokenize as tokenize_simple
from .catalogue import CandidateRepository
from .enums import ClaimPredicate, RetrievalMethod
from .models import (
    Candidate,
    CandidateQuery,
    CatalogueProduct,
    Claim,
    Observation,
    ProcessingContext,
    ProductHypothesis,
)


def _exact_identifier_candidates(
    claims: Sequence[Claim],
    hypotheses: Sequence[ProductHypothesis],
    repository: CandidateRepository,
    context: ProcessingContext,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    if not hypotheses:
        return candidates
    fallback_hypothesis_id = hypotheses[0].hypothesis_id
    seen_products: set[str] = set()

    for predicate, identifier_type, method in (
        (ClaimPredicate.MPN, "mpn", RetrievalMethod.EXACT_MPN),
        (ClaimPredicate.GTIN, "gtin", RetrievalMethod.EXACT_GTIN),
    ):
        for claim in claims:
            if claim.predicate is not predicate:
                continue
            matches = repository.get_by_identifier(
                identifier_type=identifier_type,
                value=str(claim.value),
                knowledge_version=context.knowledge_version,
            )
            for product in matches:
                if product.catalogue_product_id in seen_products:
                    continue
                seen_products.add(product.catalogue_product_id)
                candidates.append(
                    Candidate(
                        candidate_instance_id=context.id_factory(),
                        catalogue_product_id=product.catalogue_product_id,
                        hypothesis_id=fallback_hypothesis_id,
                        retrieval_method=method,
                        retrieval_rank=0,
                        retrieval_score=100.0,
                        matched_fields=(identifier_type,),
                        knowledge_version=context.knowledge_version,
                    )
                )
    return candidates


def _structured_field_agreement(
    hypothesis: ProductHypothesis, product: CatalogueProduct
) -> tuple[float, tuple[str, ...]]:
    matched: list[str] = []
    total = 0
    agree = 0
    if hypothesis.family is not None or hypothesis.compatibility_target is not None:
        total += 1
        target = hypothesis.family or hypothesis.compatibility_target
        if target is not None and (
            target == product.family or target in product.compatibility_targets
        ):
            agree += 1
            matched.append("family")
    if hypothesis.product_type is not None:
        total += 1
        if hypothesis.product_type == product.product_type:
            agree += 1
            matched.append("product_type")
    if hypothesis.brand is not None:
        total += 1
        if hypothesis.brand == product.brand:
            agree += 1
            matched.append("brand")
    if hypothesis.product_form is not None:
        total += 1
        if hypothesis.product_form == product.product_form:
            agree += 1
            matched.append("product_form")
    return (agree / total if total else 0.0), tuple(matched)


def retrieve_candidates(
    hypotheses: tuple[ProductHypothesis, ...],
    repository: CandidateRepository,
    context: ProcessingContext,
    *,
    observation: Observation,
    claims: tuple[Claim, ...] = (),
) -> tuple[Candidate, ...]:
    """Retrieve Candidates for ``hypotheses`` (spec section 14)."""
    if not hypotheses:
        return ()

    exact = _exact_identifier_candidates(claims, hypotheses, repository, context)

    query_text_tokens = set(tokenize_simple(observation.normalized_title))
    pool: list[tuple[ProductHypothesis, CatalogueProduct, float, tuple[str, ...]]] = []
    seen: set[tuple[str, str]] = set()

    for hypothesis in hypotheses:
        query = CandidateQuery(
            brand=hypothesis.brand,
            family=hypothesis.family or hypothesis.compatibility_target,
            model=hypothesis.model,
            variant=hypothesis.variant,
            product_form=hypothesis.product_form,
            product_type=hypothesis.product_type,
            identifiers={},
            attributes={},
            normalized_text=observation.normalized_title,
        )
        structured_matches = repository.retrieve(
            query=query,
            limit=context.max_candidates_before_rerank,
            knowledge_version=context.knowledge_version,
        )
        for product in structured_matches:
            key = (hypothesis.hypothesis_id, product.catalogue_product_id)
            if key in seen:
                continue
            seen.add(key)

            candidate_text = " ".join([product.canonical_title, *product.aliases, product.model])
            candidate_tokens = set(tokenize_simple(candidate_text))
            exact_overlap = (
                len(query_text_tokens & candidate_tokens) / len(candidate_tokens)
                if candidate_tokens
                else 0.0
            )
            token_set = fuzz.token_set_ratio(observation.normalized_title, candidate_text)
            token_sort = fuzz.token_sort_ratio(observation.normalized_title, candidate_text)
            struct_agreement, matched_fields = _structured_field_agreement(hypothesis, product)

            score = (
                0.45 * token_set
                + 0.25 * token_sort
                + 0.20 * (exact_overlap * 100)
                + 0.10 * (struct_agreement * 100)
            )
            score = round(min(100.0, max(0.0, score)), 2)
            pool.append((hypothesis, product, score, matched_fields))

    pool.sort(key=lambda item: item[2], reverse=True)
    reranked = pool[: context.max_candidates_before_rerank]
    reranked.sort(key=lambda item: item[2], reverse=True)
    top = reranked[: context.max_candidate_evaluations]

    candidates: list[Candidate] = list(exact)
    for rank, (hypothesis, product, score, matched_fields) in enumerate(top, start=1):
        candidates.append(
            Candidate(
                candidate_instance_id=context.id_factory(),
                catalogue_product_id=product.catalogue_product_id,
                hypothesis_id=hypothesis.hypothesis_id,
                retrieval_method=RetrievalMethod.FUZZY_TITLE_MATCH,
                retrieval_rank=rank,
                retrieval_score=score,
                matched_fields=matched_fields,
                knowledge_version=context.knowledge_version,
            )
        )
    return tuple(candidates)
