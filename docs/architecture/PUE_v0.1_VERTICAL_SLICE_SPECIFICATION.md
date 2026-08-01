# Product Understanding Engine v0.1 — Vertical Slice Specification

**Status:** Ready for implementation  
**Version:** 0.1  
**Date:** 29 July 2026  
**Project:** Digital Arbitrage  
**Primary goal:** Build and validate the smallest end-to-end Product Understanding Engine that produces useful, traceable product-understanding decisions from marketplace listings.

---

## 1. Purpose

This document converts the Product Understanding Engine manuscript and Reference Architecture into a deliberately narrow implementation specification.

It is not another general architecture document. It defines the exact first slice to build, the initial decisions required to build it, the tests that prove it works, and the features that must remain deferred.

The vertical slice must prove that the following reasoning chain can operate end to end:

```text
Observation
    ↓
Evidence
    ↓
Claim
    ↓
Product Hypothesis
    ↓
Candidate Retrieval
    ↓
Candidate Evaluation
    ↓
Decision
    ↓
Explanation
```

The slice succeeds when it can reliably distinguish a complete product from accessories, components, packaging, compatible items and unresolved listings while preserving the evidence and reasoning behind every result.

The first implementation is not expected to solve product understanding generally. It must create a working foundation that can be measured and improved without requiring architectural replacement.

---

## 2. Product Outcome

For one normalized marketplace listing, the vertical slice must produce a structured product-understanding result answering:

1. What does the listing most likely represent?
2. At what identification level is that conclusion justified?
3. Which evidence supports it?
4. Which evidence contradicts it?
5. Which candidate products were considered?
6. Why was the selected candidate preferred or rejected?
7. What remains unresolved?
8. Is direct comparison with the searched complete product structurally valid?
9. Should the system identify, classify, remain ambiguous or abstain?

The PUE does not decide whether an item should be purchased. Profitability, expected resale price, return on investment and recommendation scoring remain downstream.

Commercial information may affect processing priority later. It must not affect product identity.

---

## 3. Scope of the First Slice

### 3.1 Initial domain

The first slice covers a constrained graphics-hardware domain:

- desktop graphics cards;
- laptop or mobile graphics processors where listings describe them as products;
- graphics-card water blocks;
- replacement fans and coolers;
- backplates;
- power adapters and cables;
- mounting brackets;
- retail boxes and packaging;
- compatible accessories;
- incomplete or “for parts” graphics cards;
- simple bundles containing a graphics card and related items.

The primary product families used in the seed catalogue should include representative products from:

- NVIDIA GeForce RTX 30 and RTX 40 families;
- AMD Radeon RX 6000 and RX 7000 families;
- Intel Arc families.

The slice does not need comprehensive global GPU coverage.

### 3.2 Initial input profile

The mandatory input is a normalized listing containing:

- provider;
- provider listing identifier;
- raw title;
- normalized title;
- optional raw description;
- optional structured attributes;
- optional provider category;
- optional condition;
- acquisition timestamp.

Images are outside the first mandatory slice. Image references may be preserved, but no OCR or vision processing is required.

### 3.3 Initial execution mode

The first slice is:

- local;
- deterministic;
- title-first;
- single-process;
- capable of batch execution;
- based on a hand-seeded, versioned candidate catalogue;
- persisted in the project’s existing SQLite infrastructure or a dedicated local SQLite database;
- initially run in shadow mode alongside the existing title classifier.

### 3.4 Out of scope

The first slice does not require:

- an LLM;
- a multimodal model;
- OCR;
- image storage;
- a vector database;
- semantic embeddings;
- distributed queues;
- microservices;
- Kubernetes;
- autonomous learning;
- a human-review application;
- live catalogue hot-swapping;
- a full knowledge graph;
- probabilistic inference;
- a calibrated universal confidence score;
- automatic rule modification;
- production-scale legal clearance for every provider;
- processing one million live listings per day.

These capabilities may be introduced only after measured failures justify them.

---

## 4. Success Criteria

The vertical slice is complete when all of the following are true.

### 4.1 Functional completion

- A normalized listing can be processed through all eight reasoning stages.
- Every material Claim references supporting Evidence.
- At least one Product Hypothesis is created for a usable listing.
- Candidate Retrieval can return zero, one or many Candidates.
- Candidate Evaluation records agreements, contradictions and missing information.
- Decision Formation supports exact, partial, classified, ambiguous and abstaining outcomes.
- Explanation Generation produces an evidence-grounded explanation.
- A complete Reasoning Record can be stored and replayed.

### 4.2 Product protection

The slice must not:

- identify a water block as a complete graphics card;
- identify packaging as the contained product;
- identify an accessory merely because the title contains a prominent product name;
- force an exact variant where decisive attributes are absent;
- convert a technical processing failure into a low-confidence product identity;
- use profitability as product evidence.

### 4.3 Evaluation gate

The initial release gate requires:

- all mandatory acceptance cases passing;
- zero known accessory-to-complete-product errors in the release benchmark;
- zero known packaging-to-complete-product errors in the release benchmark;
- exact Candidate Retrieval recall reported separately from Decision accuracy;
- every wrong or abstaining Decision traceable to the stage that caused it;
- deterministic replay producing an equivalent Decision under the same capability and knowledge versions.

### 4.4 Performance diagnostic

Correctness is the release gate. Performance is measured from the beginning.

The first diagnostic target is:

- at least 25 title-only listings per second in local batch execution, excluding provider acquisition;
- no unbounded memory growth over a 10,000-listing synthetic run;
- stage-level timing recorded for extraction, retrieval, evaluation and persistence.

Failure to reach the diagnostic target is not automatically a release blocker unless the design itself creates obvious scaling debt.

---

## 5. Integration with the Existing Repository

### 5.1 Package location

Create a new package:

```text
src/digital_arbitrage/pue/
```

Recommended structure:

```text
pue/
├── __init__.py
├── models.py
├── enums.py
├── validation.py
├── admission.py
├── evidence.py
├── claims.py
├── hypotheses.py
├── catalogue.py
├── retrieval.py
├── evaluation.py
├── decisions.py
├── explanations.py
├── orchestration.py
├── persistence.py
├── policies.py
└── version.py
```

Tests should live under:

```text
tests/pue/
```

Fixtures should live under:

```text
tests/fixtures/pue/
```

The exact file layout may change during implementation, but the component boundaries must remain recognizable.

### 5.2 Initial pipeline position

The target logical pipeline is:

```text
Provider acquisition
    ↓
Normalization
    ↓
PUE
    ↓
Cross-listing product matching and comparability
    ↓
Deduplication appropriate to product identity
    ↓
Commercial scoring
```

Exact source-level duplicate suppression may occur before the PUE where it is based on provider identity or an identical source fingerprint.

Semantic deduplication must not group listings as the same product before product form and identity have been understood.

### 5.3 Shadow-mode introduction

The first PUE release should not immediately replace the current title classifier.

During the first benchmark period:

- the existing classifier continues producing its current output;
- the PUE runs alongside it;
- outputs are stored independently;
- disagreements are measured;
- no downstream purchase or recommendation behavior changes solely because of the new PUE result.

After the benchmark gate is passed, the PUE may begin supplying product-form and comparability protection to downstream matching.

### 5.4 Existing classifier adapter

The current deterministic classifier may be reused as a PUE input through an adapter.

It may contribute:

- Evidence describing matched product-form terms; or
- a proposed product-form Claim marked `PROPOSED`.

It must not directly publish the final PUE Decision.

The adapter must preserve:

- classifier version;
- matched rule or pattern;
- source text span where available;
- original classifier label;
- original deterministic score.

The existing 0–100 classifier confidence must not be presented as calibrated PUE Decision confidence.

---

## 6. Implementation Decisions

The following decisions apply to v0.1.

| Decision | v0.1 choice | Status |
|---|---|---|
| Language | Existing project Python version | Fixed for slice |
| Object model | Frozen standard-library dataclasses with slots | Provisional ADR |
| Validation | Explicit constructors and validation functions | Provisional ADR |
| Persistence | SQLite with JSON reasoning payloads | Fixed for slice |
| Catalogue | Hand-seeded versioned JSON catalogue | Fixed for slice |
| Fuzzy matching | RapidFuzz where already available or added explicitly | Fixed for slice |
| Full-text search | Not required initially | Deferred |
| Vector retrieval | Not required | Deferred |
| LLM or VLM | Not required | Deferred |
| Images | References only | Deferred |
| Identifier format | UUID for object identity; content fingerprints for deduplication | Fixed for slice |
| Runtime | Single process with batch wrappers | Fixed for slice |
| Confidence | Named dimensions and policy outcomes, not probability | Fixed for slice |
| Learning | Offline benchmark and manual release only | Fixed for slice |

### 6.1 Why dataclasses first

The first slice should use:

```python
@dataclass(frozen=True, slots=True)
```

This choice:

- introduces no unnecessary dependency;
- aligns with a small deterministic implementation;
- supports immutability;
- is easy to serialize and test;
- can later be adapted behind stable contracts if Pydantic, msgspec or another schema technology proves worthwhile.

The object contract matters more than the library.

A benchmarked migration to another schema library is permitted later without changing object meaning.

### 6.2 Why SQLite first

The existing project already uses SQLite-based history.

SQLite is sufficient for:

- the first catalogue;
- reasoning-case persistence;
- replay;
- benchmark outputs;
- local inspection;
- safe transactional writes.

DuckDB, Parquet, Polars, BM25 extensions and other analytical tools remain candidates for later measured needs. They are not mandatory to prove product understanding.

---

## 7. Common Conventions

### 7.1 Object identity

Every material reasoning object receives a UUID identifier.

Examples:

- `observation_id`;
- `evidence_id`;
- `claim_id`;
- `hypothesis_id`;
- `candidate_instance_id`;
- `candidate_evaluation_id`;
- `decision_id`;
- `explanation_id`;
- `case_id`.

Object identifiers have no product meaning.

### 7.2 Source fingerprint

A deterministic source fingerprint supports duplicate detection.

For v0.1 it should be derived from stable normalized fields such as:

```text
provider
provider_listing_id
normalized title
normalized description when present
selected structured attributes
```

The fingerprint is used for reuse and duplicate checks. It does not replace object identity.

### 7.3 Version references

Every Reasoning Record must include:

- PUE capability version;
- decision-policy version;
- catalogue knowledge version;
- classifier-adapter version where used;
- schema version.

Initial values may be:

```text
pue_capability_version = "pue-0.1.0"
decision_policy_version = "gpu-policy-0.1.0"
knowledge_version = "gpu-seed-0.1.0"
schema_version = "0.1"
```

### 7.4 Immutability

Objects that have entered a completed Reasoning Record must not be mutated.

Corrections or reruns create new objects and a new Decision.

Operational status may be recorded separately from immutable reasoning content.

### 7.5 Enumerations

Enumerations must be explicit and serialized by stable string value.

Unknown future values must not silently map to an existing meaning.

---

## 8. Minimum Object Model

### 8.1 Observation

An `Observation` is the preserved PUE representation of the source listing.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    case_id: str
    provider: str
    provider_listing_id: str
    raw_title: str
    normalized_title: str
    raw_description: str | None
    raw_category: str | None
    raw_condition: str | None
    raw_attributes: Mapping[str, object]
    image_refs: tuple[str, ...]
    acquired_at: datetime
    source_fingerprint: str
    schema_version: str
```

Rules:

- `raw_title` is never silently rewritten.
- `normalized_title` remains distinguishable from `raw_title`.
- Missing optional fields are represented as `None` or an empty immutable collection.
- Seller names, contact information and unrelated personal data should not be copied into the PUE Observation.
- Price may remain attached to the upstream listing but is not required in the PUE reasoning object for identity.

### 8.2 Evidence

Evidence records something detected in the Observation.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    observation_id: str
    evidence_type: EvidenceType
    raw_value: str
    normalized_value: str | int | float | bool | None
    source_field: str
    source_start: int | None
    source_end: int | None
    extraction_method: str
    extraction_confidence: float | None
    polarity_hint: EvidencePolarity | None
    capability_version: str
```

Initial `EvidenceType` values:

```text
BRAND_TOKEN
PRODUCT_FAMILY_TOKEN
MODEL_TOKEN
VARIANT_TOKEN
MPN_TOKEN
GTIN_TOKEN
CAPACITY_VALUE
PRODUCT_FORM_TERM
PRODUCT_TYPE_TERM
COMPATIBILITY_TERM
EXCLUSION_TERM
CONDITION_TERM
BUNDLE_TERM
PACKAGING_TERM
STRUCTURED_ATTRIBUTE
CLASSIFIER_OUTPUT
```

Initial `EvidencePolarity` values:

```text
SUPPORTING
CONTRADICTING
QUALIFYING
NEUTRAL
UNRESOLVED
```

Extraction confidence describes detection quality only. It is not Decision confidence.

### 8.3 Claim

A Claim is a product-relevant proposition supported by Evidence.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    observation_id: str
    predicate: ClaimPredicate
    value: str | int | float | bool
    status: ClaimStatus
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    qualifying_evidence_ids: tuple[str, ...]
    support_level: SupportLevel
    created_by: str
    capability_version: str
```

Initial `ClaimPredicate` values:

```text
BRAND
CHIPSET_MANUFACTURER
PRODUCT_FAMILY
MODEL
VARIANT
MPN
GTIN
PRODUCT_FORM
PRODUCT_TYPE
CONDITION
CAPACITY
COMPATIBLE_WITH
BUNDLE_CONTENT
INCLUDED
NOT_INCLUDED
```

Initial `ClaimStatus` values:

```text
PROPOSED
SUPPORTED
CONTRADICTED
QUALIFIED
UNRESOLVED
REJECTED
```

Initial `SupportLevel` values:

```text
WEAK
MODERATE
STRONG
DETERMINISTIC
```

#### Trivial-Claim test

A Claim should exist only when it expresses a proposition used in reasoning.

Do not create a Claim merely to duplicate operational data that has no interpretive role.

Examples:

- Evidence: title contains `RTX 4090`.
- Claim: `PRODUCT_FAMILY = RTX 4090`.

This Claim is useful because the token is interpreted as a product-family proposition.

By contrast:

- Evidence: title length is 47 characters.

No Claim is needed unless title length later becomes a meaningful reasoning proposition.

#### Proposed Claims

A deterministic classifier, model or external component may propose a Claim.

A proposed Claim must:

- remain marked `PROPOSED`;
- reference its Evidence;
- pass Claim Validation;
- become `SUPPORTED`, `QUALIFIED`, `CONTRADICTED` or `REJECTED` before it can materially determine a final Decision.

### 8.4 Product Hypothesis

A Product Hypothesis is one coherent possible interpretation.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class ProductHypothesis:
    hypothesis_id: str
    observation_id: str
    claim_ids: tuple[str, ...]
    product_form: ProductForm
    product_type: str | None
    brand: str | None
    family: str | None
    model: str | None
    variant: str | None
    compatibility_target: str | None
    coherence: float
    evidence_coverage: float
    status: HypothesisStatus
    unresolved_fields: tuple[str, ...]
```

Initial `ProductForm` values:

```text
COMPLETE_PRODUCT
ACCESSORY
COMPONENT
REPLACEMENT_PART
COMPATIBLE_ITEM
PACKAGING_ONLY
BUNDLE
SERVICE
INCOMPLETE_PRODUCT
UNKNOWN
```

Initial `HypothesisStatus` values:

```text
ACTIVE
WEAK
CONTRADICTED
REJECTED
SUPERSEDED
```

Hypothesis generation is bounded:

- maximum three active hypotheses per case in v0.1;
- equivalent hypotheses are merged;
- impossible combinations are rejected with a recorded reason;
- broad hypotheses remain valid where specificity is unsupported.

### 8.5 Candidate

A Candidate is a retrieved known product or product concept.

The known catalogue record and the retrieval instance remain distinguishable.

Catalogue record:

```python
@dataclass(frozen=True, slots=True)
class CatalogueProduct:
    catalogue_product_id: str
    canonical_title: str
    brand: str
    chipset_manufacturer: str | None
    family: str
    model: str
    variant: str | None
    product_form: ProductForm
    product_type: str
    identifiers: Mapping[str, tuple[str, ...]]
    aliases: tuple[str, ...]
    attributes: Mapping[str, object]
    compatibility_targets: tuple[str, ...]
    knowledge_version: str
```

Retrieval instance:

```python
@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_instance_id: str
    catalogue_product_id: str
    hypothesis_id: str
    retrieval_method: RetrievalMethod
    retrieval_rank: int
    retrieval_score: float
    matched_fields: tuple[str, ...]
    knowledge_version: str
```

Initial `RetrievalMethod` values:

```text
EXACT_MPN
EXACT_GTIN
EXACT_CANONICAL_NAME
STRUCTURED_FILTER
NORMALIZED_TOKEN_MATCH
FUZZY_TITLE_MATCH
ALIAS_MATCH
```

Retrieval score is a ranking signal, not identity confidence.

### 8.6 Candidate Evaluation

A Candidate Evaluation records how well a Candidate explains the listing.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate_evaluation_id: str
    candidate_instance_id: str
    hypothesis_id: str
    agreements: tuple[ComparisonFinding, ...]
    contradictions: tuple[ComparisonFinding, ...]
    missing_information: tuple[ComparisonFinding, ...]
    identity_fit: float
    product_form_fit: float
    attribute_fit: float
    evidence_coverage: float
    hard_rejected: bool
    evaluation_outcome: CandidateOutcome
    policy_version: str
```

Finding:

```python
@dataclass(frozen=True, slots=True)
class ComparisonFinding:
    field: str
    observed_value: object
    candidate_value: object
    result: ComparisonResult
    severity: ContradictionSeverity | None
    evidence_ids: tuple[str, ...]
    explanation: str
```

`CandidateOutcome` values:

```text
STRONGLY_SUPPORTED
SUPPORTED
PROVISIONALLY_SUPPORTED
WEAKLY_SUPPORTED
INDISTINGUISHABLE
CONTRADICTED
REJECTED
UNEVALUABLE
```

### 8.7 Decision

A Decision is the formal product-understanding result.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    case_id: str
    observation_id: str
    decision_type: DecisionType
    identification_level: IdentificationLevel
    selected_hypothesis_id: str | None
    selected_candidate_instance_id: str | None
    product_form: ProductForm
    product_type: str | None
    identified_brand: str | None
    identified_family: str | None
    identified_model: str | None
    identified_variant: str | None
    alternative_candidate_ids: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    contradiction_codes: tuple[str, ...]
    abstention_reason: AbstentionReason | None
    review_recommended: bool
    comparability_status: ComparabilityStatus
    uncertainty: DecisionUncertainty
    policy_version: str
    knowledge_version: str
    capability_version: str
```

`DecisionType` values:

```text
IDENTIFIED
PARTIALLY_IDENTIFIED
CLASSIFIED
AMBIGUOUS
ABSTAINED
OUTSIDE_SUPPORTED_DOMAIN
PROCESSING_FAILED
```

`ESCALATED` is not a Decision type. Escalation is a runtime action taken before a final Decision.

`IdentificationLevel` values:

```text
EXACT_CATALOGUE_PRODUCT
VARIANT
MODEL
FAMILY
BRAND_AND_PRODUCT_TYPE
PRODUCT_TYPE
UNKNOWN
```

`ComparabilityStatus` values:

```text
DIRECTLY_COMPARABLE
COMPARABLE_AT_BROADER_LEVEL
NOT_COMPARABLE_PRODUCT_FORM
NOT_COMPARABLE_BUNDLE
NOT_COMPARABLE_CONDITION
INSUFFICIENT_INFORMATION
NOT_ASSESSED
```

The comparability signal describes structural product comparability. It does not determine profitability.

### 8.8 Decision uncertainty

The first slice uses named dimensions:

```python
@dataclass(frozen=True, slots=True)
class DecisionUncertainty:
    observation_quality: UncertaintyBand
    claim_support: UncertaintyBand
    candidate_fit: UncertaintyBand
    evidence_coverage: UncertaintyBand
    contradiction_level: UncertaintyBand
    distinguishability: UncertaintyBand
    calibration_status: CalibrationStatus
```

Initial bands:

```text
LOW
MODERATE
HIGH
UNKNOWN
```

Initial calibration status:

```text
UNCALIBRATED
PROVISIONAL
EVALUATED
OUTSIDE_EVALUATED_DOMAIN
```

These fields are not combined into a probability in v0.1.

### 8.9 Explanation

An Explanation must be derived from the actual reasoning record.

Required fields:

```python
@dataclass(frozen=True, slots=True)
class Explanation:
    explanation_id: str
    decision_id: str
    summary: str
    supporting_points: tuple[str, ...]
    contradictory_points: tuple[str, ...]
    unresolved_points: tuple[str, ...]
    rejected_alternatives: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    profile: ExplanationProfile
```

Initial profile:

```text
OPERATOR
```

Audit and machine profiles may be derived from the complete Reasoning Record later.

### 8.10 Reasoning Record

The top-level persisted unit is:

```python
@dataclass(frozen=True, slots=True)
class ReasoningRecord:
    case_id: str
    observation: Observation
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]
    hypotheses: tuple[ProductHypothesis, ...]
    candidates: tuple[Candidate, ...]
    candidate_evaluations: tuple[CandidateEvaluation, ...]
    decision: Decision
    explanation: Explanation
    operational_metrics: Mapping[str, object]
    schema_version: str
    created_at: datetime
```

The record must serialize without hidden component state.

### 8.11 Product Understanding Result

`ProductUnderstandingResult` is the stable publication envelope. It is not a new reasoning stage.

```python
@dataclass(frozen=True, slots=True)
class ProductUnderstandingResult:
    result_schema_version: str
    case_id: str
    observation_id: str
    decision_id: str
    status: DecisionType
    identification_level: IdentificationLevel
    product_form: ProductForm
    product_type: str | None
    catalogue_product_id: str | None
    identity: Mapping[str, object]
    comparability_status: ComparabilityStatus
    unresolved_fields: tuple[str, ...]
    review_recommended: bool
    explanation_summary: str
    reasoning_record_ref: str
```

It exposes the Decision without replacing the detailed reasoning objects.

---

## 9. Evidence Extraction Specification

### 9.1 Mandatory extractors

The first slice implements deterministic extractors for:

- brand names and aliases;
- chipset manufacturers;
- GPU families and models;
- common manufacturer part-number patterns;
- memory capacities;
- product-form terms;
- compatibility terms;
- packaging terms;
- exclusion terms;
- bundle terms;
- condition terms.

### 9.2 Initial term groups

Examples of complete-product terms:

```text
graphics card
gpu
video card
founders edition
gaming oc
complete card
```

Examples of accessory or component terms:

```text
water block
waterblock
cooling block
backplate
fan
cooler
heatsink
bracket
riser cable
power adapter
power cable
mount
housing
```

Examples of packaging terms:

```text
box only
empty box
retail box
packaging only
original box
no card
```

Examples of compatibility terms:

```text
for RTX 4090
compatible with RTX 4090
fits RTX 4090
replacement for
designed for
```

Examples of exclusion terms:

```text
not included
GPU not included
card not included
for parts
spares or repair
non-working
damaged
```

The term lists are versioned Knowledge Artifacts rather than permanent truths.

### 9.3 Normalization rules

Normalization should include:

- Unicode normalization;
- case folding;
- separator normalization;
- whitespace collapse;
- canonical spacing for model tokens;
- capacity normalization;
- punctuation handling that preserves meaningful part numbers;
- alias mapping such as `FE → Founders Edition` only when context supports it.

Normalization must not invent an unobserved model suffix or variant.

### 9.4 Extraction output requirements

Each extracted item must include:

- raw value;
- normalized value;
- source field;
- character span where practical;
- extraction method;
- extraction confidence or deterministic flag;
- version.

### 9.5 Recall policy

Extraction should favor recovering plausible product-relevant signals, but it must remain bounded.

The first slice does not generate every conceivable token as Evidence.

A token is emitted only where it belongs to a defined Evidence type or known term group.

---

## 10. Claim Construction and Validation

### 10.1 Construction rules

Claims are created from Evidence using explicit mappings.

| Evidence | Claim |
|---|---|
| Brand token `ASUS` | `BRAND = ASUS` |
| Model token `RTX 4090` | `PRODUCT_FAMILY = RTX 4090` |
| Term `water block` | `PRODUCT_FORM = COMPONENT` and `PRODUCT_TYPE = GPU_WATER_BLOCK` |
| Phrase `for RTX 4090` | `COMPATIBLE_WITH = RTX 4090` |
| Phrase `box only` | `PRODUCT_FORM = PACKAGING_ONLY` |
| Phrase `GPU not included` | `NOT_INCLUDED = GRAPHICS_CARD` |
| MPN pattern validated against catalogue | `MPN = <value>` |

### 10.2 Validation rules

Claim Validation must check:

- supporting Evidence exists;
- the Claim value has an allowed type;
- compound Claims are split where practical;
- incompatible Claims are retained as a conflict rather than silently merged;
- proposed Claims from the classifier are independently validated;
- Evidence from the same source fragment is not counted as independent confirmation;
- explicit exclusion terms outweigh broad category or family mentions for product form.

### 10.3 Product-form precedence

For v0.1, explicit product-form and exclusion evidence receives special protection.

Examples:

- `water block` prevents a complete graphics-card hypothesis unless separate strong Evidence indicates the card is included.
- `box only` prevents a complete-product Decision.
- `GPU not included` prevents a complete graphics-card Decision.
- `replacement fan` creates a replacement-part hypothesis even when the title contains a GPU model.
- `compatible with RTX 4090` describes a relationship, not identity.

This is a policy safeguard, not a universal scoring shortcut.

---

## 11. Hypothesis Generation

### 11.1 Initial hypothesis templates

The generator may create up to three active hypotheses.

#### Complete-product hypothesis

Created when Evidence supports a graphics card as the item being sold.

Example:

```text
brand = ASUS
family = RTX 4090
product_form = COMPLETE_PRODUCT
product_type = GRAPHICS_CARD
```

#### Accessory/component hypothesis

Created when Evidence indicates:

- water block;
- fan;
- cooler;
- backplate;
- bracket;
- cable;
- adapter;
- housing;
- replacement component.

#### Packaging hypothesis

Created when Evidence indicates:

- box only;
- empty box;
- packaging only;
- original box without product.

#### Compatible-item hypothesis

Created when the main product name appears primarily as a compatibility target.

#### Bundle hypothesis

Created when multiple included products are explicitly described.

### 11.2 Coherence

Starting coherence calculation may be rule-based:

- `1.0`: no internal contradiction;
- `0.7`: minor unresolved attribute conflict;
- `0.4`: material but potentially reconcilable conflict;
- `0.0`: impossible combination.

These values are policy signals, not calibrated probabilities.

### 11.3 Evidence coverage

Coverage is:

```text
supported decision-relevant fields
÷
required decision-relevant fields for the requested identification level
```

For a family-level graphics-card Decision, required fields may include:

- product form;
- product type;
- family.

For exact variant identification, required fields may additionally include:

- brand or board partner;
- model;
- variant or MPN;
- critical capacity where variants differ.

### 11.4 Bounded branching

Branching is permitted when:

- two variants differ on an unobserved critical attribute;
- product form remains genuinely ambiguous;
- the title could describe a bundle or one included item;
- conflicting model values are both supported.

Branching must not create arbitrary combinations of every weak Claim.

---

## 12. Seed Candidate Catalogue

### 12.1 Catalogue strategy

The first catalogue must be hand-seeded and version-controlled in the repository.

Recommended location:

```text
data/pue/catalogues/gpu_seed_v0.1.json
```

The catalogue should contain approximately 30–50 deliberately chosen records.

It should include:

- reference graphics cards;
- board-partner variants;
- at least two product families with indistinguishable sub-variants;
- laptop/mobile variants;
- representative water blocks;
- representative replacement fans or coolers;
- packaging-only concepts;
- compatible cables or adapters.

The first catalogue is an evaluation instrument, not a production catalogue.

### 12.2 Required catalogue cases

At minimum, include:

- NVIDIA RTX 4090 Founders Edition;
- two or more ASUS/MSI/Gigabyte RTX 4090 variants;
- RTX 4080 and RTX 4080 SUPER variants;
- RTX 4070 family examples;
- one RTX 30-series family with several memory variants;
- AMD RX 7900 XTX and RX 7800 XT examples;
- Intel Arc A770 and A750 examples;
- a mobile GPU product concept;
- a GPU water block;
- an empty retail box concept;
- a replacement fan or cooler;
- a compatible power adapter.

### 12.3 Provenance and licensing

Every catalogue record must include:

- source description;
- source URL or reference where permitted;
- date admitted;
- license or usage note;
- curator;
- knowledge version.

Do not depend on an external dataset until its availability, license and suitability have been verified.

A future public or commercial catalogue may replace the hand-seeded catalogue behind the same `CandidateRepository` interface.

---

## 13. Candidate Repository Contract

The reasoning components must not contain direct SQL.

Use an interface:

```python
class CandidateRepository(Protocol):
    def get_by_identifier(
        self,
        *,
        identifier_type: str,
        value: str,
        knowledge_version: str,
    ) -> Sequence[CatalogueProduct]: ...

    def retrieve(
        self,
        *,
        query: CandidateQuery,
        limit: int,
        knowledge_version: str,
    ) -> Sequence[RetrievedCatalogueProduct]: ...
```

Candidate query:

```python
@dataclass(frozen=True, slots=True)
class CandidateQuery:
    brand: str | None
    family: str | None
    model: str | None
    variant: str | None
    product_form: ProductForm
    product_type: str | None
    identifiers: Mapping[str, str]
    attributes: Mapping[str, object]
    normalized_text: str
```

The first repository may load JSON into memory.

SQLite indexing may be added where useful without changing the interface.

---

## 14. Candidate Retrieval

### 14.1 Retrieval stages

The first implementation uses the following sequence.

#### Stage 1 — Exact identifiers

Check:

- MPN;
- GTIN;
- UPC/EAN where present.

An exact identifier match produces a high-priority Candidate, but Candidate Evaluation still checks product form and contradictions.

#### Stage 2 — Structured filtering

Filter by available strong fields:

- product form;
- product type;
- family;
- brand;
- chipset manufacturer;
- critical capacity.

Missing fields do not exclude Candidates.

Explicit incompatible fields may exclude Candidates.

#### Stage 3 — Normalized token retrieval

Compare the listing’s normalized tokens with:

- canonical title;
- model;
- aliases;
- variant strings.

#### Stage 4 — Fuzzy re-ranking

Use RapidFuzz for remaining Candidates.

Initial measures:

- `token_set_ratio`;
- `token_sort_ratio`;
- normalized exact-token overlap.

### 14.2 Initial retrieval score

A provisional ranking score may be:

```text
0.45 × token_set_ratio
+ 0.25 × token_sort_ratio
+ 0.20 × exact important-token overlap
+ 0.10 × structured-field agreement
```

Scores must be normalized to `0–100`.

This score ranks Candidates only. It does not publish identity.

### 14.3 Candidate limits

Initial limits:

- exact identifier: all exact matches, expected one;
- structured and lexical retrieval: top 20;
- after fuzzy reranking: top 10;
- Candidate Evaluation: top 10.

Limits are configurable and benchmarked.

### 14.4 Zero-Candidate behavior

Zero Candidates is valid.

The system may then:

- publish a `CLASSIFIED` Decision if product form and type are adequately understood;
- publish `OUTSIDE_SUPPORTED_DOMAIN`;
- abstain with `NO_SUITABLE_CANDIDATE`;
- record a catalogue-gap Learning Record later.

It must not force the nearest known product.

### 14.5 Vector-search trigger

Vector retrieval remains disabled.

It may be investigated only when the private benchmark demonstrates that structured, lexical and fuzzy retrieval fail to include the correct Candidate often enough to materially limit the product.

No universal trigger percentage is fixed in this document. The decision must be based on measured Candidate recall, cost and category failure analysis.

---

## 15. Candidate Evaluation Policy

### 15.1 Evaluation dimensions

Every Candidate is evaluated on:

- identity agreement;
- product-form agreement;
- product-type agreement;
- brand agreement;
- family/model agreement;
- variant agreement;
- identifier agreement;
- critical-attribute agreement;
- compatibility relationship;
- Evidence coverage;
- contradiction severity.

### 15.2 Missing information

Missing information is neutral.

Examples:

- listing does not state VRAM;
- listing omits board partner;
- no model suffix is present.

The Candidate is not penalized as contradicted merely because the listing is incomplete.

Missing critical information may prevent exact identification.

### 15.3 Hard contradictions

The following are hard rejection rules in v0.1:

1. Exact MPN explicitly disagrees with Candidate MPN.
2. Listing product form is strongly supported as accessory, component, packaging or service while Candidate is a complete graphics card.
3. Listing explicitly states that the GPU/card is not included while Candidate is the complete GPU.
4. Listing is strongly supported as packaging only while Candidate is the contained product.
5. Explicit model family conflicts with Candidate family and the conflict cannot be explained as compatibility.
6. Desktop and mobile form conflict where the distinction is explicit and material.
7. Candidate represents identity while the listing Evidence describes compatibility only.

Hard rejection remains visible in the Candidate Evaluation.

### 15.4 Soft contradictions

Soft contradictions may reduce ranking without forcing rejection:

- board partner differs but the listing may use a generic title;
- color differs;
- factory-overclocked suffix is unresolved;
- condition is missing or inconsistent;
- noncritical bundle contents differ.

### 15.5 Starting evaluation score

A transparent v0.1 scoring model may use:

| Dimension | Maximum points |
|---|---:|
| Exact validated identifier | 100 and short-circuit to validation |
| Exact model/family | 40 |
| Product-form agreement | 25 |
| Brand/board-partner agreement | 15 |
| Variant agreement | 10 |
| Critical-attribute agreement | 10 |

Rules:

- hard contradiction → Candidate rejected regardless of score;
- missing value → no points and no contradiction;
- exact identifier match still requires no product-form contradiction;
- score is an evaluation aid, not a probability.

### 15.6 Worked example: high similarity rejected

Listing:

```text
EK Quantum Vector RTX 4090 Water Block Full Cover
```

Evidence:

```text
E1: PRODUCT_FAMILY_TOKEN = RTX 4090
E2: PRODUCT_FORM_TERM = water block
E3: PRODUCT_TYPE_TERM = full-cover cooling block
```

Claims:

```text
C1: PRODUCT_FAMILY = RTX 4090, strongly supported
C2: PRODUCT_FORM = COMPONENT, deterministic
C3: PRODUCT_TYPE = GPU_WATER_BLOCK, deterministic
C4: COMPATIBLE_WITH = RTX 4090, strongly supported
```

Candidate A:

```text
NVIDIA GeForce RTX 4090 Founders Edition graphics card
retrieval similarity = 94
```

Candidate A evaluation:

```text
family agreement = +40
brand unresolved = +0
product-form contradiction = HARD REJECTION
compatibility is not identity = HARD REJECTION
outcome = REJECTED
```

Candidate B:

```text
EK full-cover water block compatible with selected RTX 4090 boards
retrieval similarity = 86
```

Candidate B evaluation:

```text
family relationship agreement = +40
product-form agreement = +25
product-type agreement = supported
exact board variant missing
outcome = PROVISIONALLY_SUPPORTED
```

Decision:

```text
CLASSIFIED as an RTX 4090-compatible GPU water block.
Exact water-block variant unresolved.
NOT_COMPARABLE_PRODUCT_FORM with complete RTX 4090 graphics cards.
```

This example proves that retrieval similarity cannot override product-form contradiction.

---

## 16. Decision Policy

### 16.1 Decision sequence

Decision Formation evaluates:

1. Did the case complete operationally?
2. Is there at least one coherent Product Hypothesis?
3. Were plausible Candidates retrieved where catalogue identity is required?
4. Did hard contradictions reject the leading Candidates?
5. Does one Candidate materially outperform the alternatives?
6. Is the Evidence sufficient for the requested identification level?
7. Are the remaining Candidates distinguishable?
8. Would broader identification be justified?
9. Is classification possible without a catalogue match?
10. Should the engine abstain?

### 16.2 Exact identification

Publish `IDENTIFIED / EXACT_CATALOGUE_PRODUCT` when:

- the selected Candidate is not hard rejected;
- exact identifier agreement exists, or all decision-critical identity fields agree;
- no materially plausible competing Candidate remains;
- the exact variant is supported rather than guessed;
- Evidence coverage is sufficient for exact identity.

### 16.3 Partial identification

Publish `PARTIALLY_IDENTIFIED` when:

- product form and broader identity are well supported;
- exact variant or sub-variant cannot be distinguished;
- no contradiction invalidates the broader identity.

Example:

```text
NVIDIA GeForce RTX 4090 graphics card.
Exact board-partner model unresolved.
```

### 16.4 Classified

Publish `CLASSIFIED` when:

- product form and product type are sufficiently supported;
- exact catalogue identity is absent, unnecessary or unsupported.

Example:

```text
RTX 4090-compatible GPU water block.
Exact water-block model unresolved.
```

### 16.5 Ambiguous

Publish `AMBIGUOUS` when:

- two or more materially different interpretations remain plausible;
- available Evidence cannot distinguish them;
- broader classification would conceal a decision-critical distinction.

Example:

```text
Could be a complete graphics card bundled with a water block,
or a water block sold alone.
```

### 16.6 Abstained

Publish `ABSTAINED` when:

- Evidence is insufficient;
- no suitable Candidate exists and no useful classification is justified;
- source quality is too low;
- material contradictions remain unresolved;
- processing limits are reached;
- the case is outside the evaluated domain but not clearly outside the supported category.

Initial `AbstentionReason` values:

```text
INSUFFICIENT_EVIDENCE
UNRESOLVED_CONTRADICTION
CANDIDATES_INDISTINGUISHABLE
NO_SUITABLE_CANDIDATE
SOURCE_QUALITY_TOO_LOW
PROCESSING_LIMIT_REACHED
UNKNOWN_PRODUCT_PATTERN
```

No universal numeric score threshold is fixed in v0.1.

Thresholds must be tuned against the labelled benchmark and recorded in a versioned Decision Policy.

### 16.7 Outside supported domain

Publish `OUTSIDE_SUPPORTED_DOMAIN` when the listing is clearly not part of the supported graphics-hardware domain.

### 16.8 Processing failed

Publish `PROCESSING_FAILED` only for operational failure.

Examples:

- malformed object prevented validation;
- catalogue file could not be loaded;
- persistence failed after retry;
- unexpected component exception prevented completion.

A processing failure must not be interpreted as product uncertainty.

### 16.9 Comparability policy

For v0.1:

- complete graphics card vs the same complete graphics card → potentially directly comparable;
- same family but unresolved variant → comparable only at broader level;
- water block vs graphics card → not comparable by product form;
- packaging vs graphics card → not comparable by product form;
- replacement fan vs graphics card → not comparable by product form;
- bundle vs single product → not directly comparable;
- “for parts” complete card vs functioning card → condition comparability remains restricted;
- unresolved product form → insufficient information.

---

## 17. Explanation Generation

### 17.1 Template-based explanations

The first slice uses deterministic templates.

Example exact identification:

```text
Identified as ASUS TUF Gaming GeForce RTX 4090 OC.
The title contains the matching model and board-partner variant,
and the manufacturer part number matches the catalogue record.
No material contradiction was found.
```

Example partial identification:

```text
Identified as an NVIDIA GeForce RTX 4090 graphics card.
The exact board-partner variant could not be established because
the listing does not contain a manufacturer or part number.
```

Example classified accessory:

```text
Classified as an RTX 4090-compatible water block, not a complete
graphics card. “Water block” describes the item being sold, while
“RTX 4090” describes compatibility.
```

Example abstention:

```text
The listing is probably a graphics card, but the model cannot be
identified reliably. Several candidate families remain plausible
and no decisive identifier or model term is available.
```

### 17.2 Faithfulness validation

Before publication, validate that:

- selected identity matches the Decision;
- every cited Evidence ID exists;
- no rejected Candidate is described as selected;
- uncertainty is not omitted;
- the explanation does not add unsupported attributes;
- product form matches the Decision;
- abstention reason is stated where applicable.

### 17.3 No generative explanation in v0.1

An LLM is not needed to produce useful first-slice explanations.

Generative rewriting may be evaluated later for readability, but the structured explanation must remain authoritative.

---

## 18. Runtime Orchestration

### 18.1 Case states

Initial runtime states:

```text
RECEIVED
ADMITTED
EXTRACTING
CONSTRUCTING_CLAIMS
GENERATING_HYPOTHESES
RETRIEVING_CANDIDATES
EVALUATING_CANDIDATES
FORMING_DECISION
GENERATING_EXPLANATION
PERSISTING
COMPLETED
FAILED
```

`ABSTAINED` and `AMBIGUOUS` are reasoning outcomes, not runtime failures.

### 18.2 Component interfaces

Each component should expose a deterministic contract.

```python
admit_observation(listing, context) -> Observation
extract_evidence(observation, context) -> tuple[Evidence, ...]
construct_claims(observation, evidence, context) -> tuple[Claim, ...]
generate_hypotheses(observation, claims, context) -> tuple[ProductHypothesis, ...]
retrieve_candidates(hypotheses, repository, context) -> tuple[Candidate, ...]
evaluate_candidates(state, repository, context) -> tuple[CandidateEvaluation, ...]
form_decision(state, policy) -> Decision
generate_explanation(state, decision) -> Explanation
publish_result(record) -> ProductUnderstandingResult
```

### 18.3 Batch wrappers

Single-case functions remain the reference behavior.

Batch wrappers should accept sequences:

```python
process_many(
    listings: Sequence[NormalizedListing],
    context: ProcessingContext,
) -> Sequence[ProductUnderstandingResult]
```

Batching must not alter case semantics.

### 18.4 Bounds

Initial limits:

- maximum three active hypotheses;
- maximum twenty retrieved Candidates before reranking;
- maximum ten Candidate Evaluations;
- one deterministic reasoning pass;
- no autonomous repeated loop;
- configurable per-case timeout;
- bounded persistence retry.

### 18.5 Escalation

The first slice has no deep-processing lane.

A case requiring unavailable OCR, image interpretation, external lookup or human review records:

- the missing capability;
- the expected value of that capability;
- whether review is recommended.

It then publishes the best justified Decision, often partial, ambiguous or abstaining.

---

## 19. Persistence and Replay

### 19.1 Persistence approach

Use SQLite with a compact case table and versioned JSON payload.

Suggested table:

```sql
CREATE TABLE IF NOT EXISTS pue_cases (
    case_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_listing_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    identification_level TEXT NOT NULL,
    product_form TEXT NOT NULL,
    selected_catalogue_product_id TEXT,
    comparability_status TEXT NOT NULL,
    reasoning_record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

Useful indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_pue_cases_listing
ON pue_cases(provider, provider_listing_id);

CREATE INDEX IF NOT EXISTS idx_pue_cases_fingerprint
ON pue_cases(source_fingerprint);

CREATE INDEX IF NOT EXISTS idx_pue_cases_versions
ON pue_cases(capability_version, policy_version, knowledge_version);
```

### 19.2 Why JSON payloads initially

JSON payloads permit the object model to evolve quickly while:

- preserving complete cases;
- supporting replay;
- avoiding premature relational schema complexity;
- allowing focused indexes on important summary fields.

A normalized relational schema may be introduced after real query and performance needs are measured.

### 19.3 Replay command

Add a developer-facing command or function:

```text
arb pue replay <case-id>
```

Replay should:

- load the original Observation;
- use specified or original capability and knowledge versions;
- run the current or requested pipeline;
- compare old and new Decisions;
- preserve both reasoning records;
- report changed Claims, Candidates, contradictions and outcome.

### 19.4 Idempotency

Processing the same source fingerprint under the same versions should produce an equivalent reasoning result.

A new Reasoning Activity may still be recorded, but duplicate completed records should be avoided unless the run is explicitly marked as evaluation or replay.

---

## 20. Initial Benchmark

### 20.1 Benchmark stages

Use two benchmark stages.

#### Stage A — Sprint 1 acceptance set

Create 20–30 hand-authored or hand-labelled cases sufficient to prove the pipeline.

#### Stage B — v0.1 release benchmark

Expand to 100–150 representative cases before the PUE affects downstream product matching.

A 300-case benchmark is a good later target, not a prerequisite for writing the first code.

### 20.2 Required benchmark strata

The release benchmark should contain:

| Stratum | Initial target |
|---|---:|
| Straightforward complete-product matches | 30 |
| Accessories/components/replacement parts | 25 |
| Packaging-only and exclusion cases | 10 |
| Missing-attribute partial identifications | 15 |
| Indistinguishable variants | 10 |
| Bundles and incomplete products | 10 |
| Contradictory listings | 10 |
| Unknown or out-of-catalogue products | 10 |
| Outside supported domain | 5 |
| Operational malformed-input cases | 5 |

These are starting targets and may overlap where a case exercises several risks.

### 20.3 Labels

Every benchmark case should include:

```text
case_id
raw input
expected product form
expected product type
acceptable identification level
expected catalogue product, if exact identity is justified
acceptable broader identities
forbidden decisions
decisive evidence
known contradictions
expected comparability status
expected abstention reason, if applicable
difficulty category
annotation source
annotation confidence
```

### 20.4 Split discipline

When the benchmark grows:

- keep development and holdout cases separate;
- group copied or near-duplicate listings together;
- avoid using holdout answers to tune rules;
- version every dataset release;
- record which cases motivated each rule.

---

## 21. Mandatory Acceptance Cases

The first implementation must include at least the following tests.

| # | Listing | Expected result |
|---:|---|---|
| 1 | `Samsung?` — not GPU domain | `OUTSIDE_SUPPORTED_DOMAIN` |
| 2 | `NVIDIA GeForce RTX 4090 Founders Edition 24GB` | Exact or model-level identification depending on catalogue evidence |
| 3 | `ASUS TUF RTX 4090 OC TUF-RTX4090-O24G` | Exact identification by validated MPN |
| 4 | `RTX 4090 Waterblock Full Cover GPU Cooling Block` | `CLASSIFIED` as component/water block; not comparable with GPU |
| 5 | `Empty RTX 4090 Founders Edition Box Only` | `CLASSIFIED` as packaging only |
| 6 | `RTX 4090 replacement fan set` | Replacement part, not complete GPU |
| 7 | `12VHPWR power adapter for RTX 4090` | Compatible accessory, not GPU |
| 8 | `RTX 4090 GPU not included — water block only` | Component; explicit exclusion controls |
| 9 | `ASUS RTX 4090 with EK water block` | Bundle or modified complete product; must not collapse to water block only without evidence |
| 10 | `NVIDIA RTX 4090` | Partial/model-level identification; exact board partner unresolved |
| 11 | `RTX 3060 12GB` with several board partners | Model-level partial identification |
| 12 | `RTX 3060` where 8GB and 12GB variants exist | Variant unresolved; no arbitrary exact selection |
| 13 | `RTX 4080 Super Gaming OC` | Correct family and likely variant where supported |
| 14 | `RTX 4080` title with structured attribute `RTX 4070` | Contradiction visible; ambiguous or abstained |
| 15 | `Laptop RTX 4090 GPU` | Mobile form; reject desktop complete-card Candidate |
| 16 | `Graphics card excellent condition` | Classified as graphics card or abstained; no invented family |
| 17 | `Apple laptop good condition` | Outside GPU domain or abstained under routing policy |
| 18 | `For parts RTX 4090 not working` | Incomplete/for-parts complete product; condition comparability restricted |
| 19 | `RTX 4090 retail box included` with clear complete-product terms | Complete-product hypothesis may survive; `box included` must not become `box only` |
| 20 | Unknown coherent GPU model absent from catalogue | Classified or partial; no forced nearest Candidate |
| 21 | Exact MPN matching Candidate but title says `box only` | Complete-product Candidate hard rejected |
| 22 | `Compatible with RTX 4090` and no sold-item noun | Classified as a non-complete `compatible_item` (or ambiguous if genuinely more than one interpretation remains plausible); never abstained - a single compatibility-only hypothesis is one coherent interpretation, not insufficient evidence. Compatibility must not become identity (Sprint 3 final narrow correction) |
| 23 | `RTX 4090 + PSU bundle` | Bundle, not directly comparable to single GPU |
| 24 | Empty title | `ABSTAINED` or input-quality handling, not technical crash |
| 25 | Malformed object | `PROCESSING_FAILED` with explicit failure category |

For every case, tests must assert not only the final Decision but also key Evidence, Claims and Candidate contradictions.

---

## 22. Evaluation Metrics

### 22.1 Primary product metrics

Report:

- product-form accuracy;
- exact identification accuracy;
- hierarchical identification accuracy;
- Candidate recall at 1, 5 and 10;
- harmful false-match rate;
- accessory-to-complete-product error rate;
- packaging-to-complete-product error rate;
- partial-identification correctness;
- abstention rate;
- avoidable abstention rate;
- comparability accuracy;
- explanation faithfulness.

### 22.2 Pipeline metrics

Report:

- Evidence extraction precision and recall for labelled fields;
- Claim support accuracy;
- correct-hypothesis inclusion rate;
- Candidate count;
- Candidate Retrieval latency;
- hard-contradiction detection rate;
- Decision distribution;
- classifier/PUE disagreement rate.

### 22.3 Operational metrics

Report:

- listings per second;
- median and 95th-percentile latency;
- persistence time;
- memory use;
- cache or reuse rate;
- failure rate;
- serialized reasoning-record size.

### 22.4 No misleading aggregate

A single overall accuracy score is insufficient.

At minimum, product-form errors and harmful false matches must be shown separately.

---

## 23. Testing Requirements

### 23.1 Unit tests

Required unit-test groups:

- normalization and term extraction;
- Evidence spans and provenance;
- Claim validation;
- incompatible Claim handling;
- hypothesis branching and merging;
- exact identifier retrieval;
- fuzzy retrieval;
- hard contradiction rules;
- partial identification;
- abstention;
- explanation faithfulness;
- serialization round trip;
- persistence;
- replay equivalence.

### 23.2 Property and invariant tests

Required invariants:

1. Raw title remains unchanged.
2. Every Claim references at least one Evidence object unless explicitly system-generated for an operational reason.
3. Every Candidate Evaluation references a Candidate and Product Hypothesis.
4. Retrieval score alone cannot produce a Decision.
5. A hard product-form contradiction rejects a complete-product Candidate.
6. A Decision cannot be more specific than its supporting Claims.
7. An Explanation cannot name a product absent from the Decision.
8. An abstention is not recorded as technical failure.
9. `ESCALATED` cannot appear as a Decision type.
10. A superseding run does not overwrite the earlier record.
11. Profit and ROI do not enter Claim or Candidate Evaluation inputs.
12. The Product Understanding Result references the underlying Decision.

### 23.3 Golden tests

Golden tests should compare complete serialized Reasoning Records for a small stable subset.

They must be reviewed carefully because harmless identifier or timestamp changes can create noisy diffs.

### 23.4 Differential tests

Run the existing title classifier and PUE on the same benchmark.

Report:

- cases both get right;
- cases PUE corrects;
- cases classifier correct and PUE worsens;
- cases where PUE abstains;
- cases where PUE prevents harmful comparability.

---

## 24. Legal, Licensing and Data Governance

### 24.1 Local prototype

The first slice should use:

- hand-seeded catalogue records;
- synthetic listings;
- listings supplied for internal evaluation under an appropriate basis;
- no persistent raw image storage;
- no unnecessary seller personal data.

This allows implementation to begin without resolving every production legal issue.

### 24.2 Live marketplace data

Before enabling a provider in the benchmark:

- review API and developer terms;
- identify permitted storage duration;
- identify restrictions on descriptions, images and derived data;
- identify deletion obligations;
- document credential handling;
- document allowed commercial use;
- identify provider attribution requirements.

### 24.3 Personal data

The PUE does not need seller identity to understand the product in v0.1.

The ingestion adapter should avoid passing:

- seller names;
- email addresses;
- phone numbers;
- exact personal addresses;
- free-form messages unrelated to product identity.

Provider and listing identifiers may be retained where operationally required.

GDPR obligations depend on the actual data, purpose and deployment. They should be reviewed before live commercial processing rather than replaced by unsupported blanket assumptions.

### 24.4 Images

The first slice does not process images.

Before persistent image use is introduced, decide:

- whether the provider permits storage;
- retention duration;
- whether a transient download is allowed;
- whether hashes or embeddings may be retained;
- whether source deletion must propagate;
- whether the image contains personal data.

“Never store images” and “always store images” are both unjustified universal policies. The decision is provider- and use-specific.

### 24.5 Catalogue and model licenses

Before importing an external catalogue or model:

- verify the exact license;
- confirm commercial use;
- confirm modification and redistribution terms;
- record attribution requirements;
- record source version and acquisition date;
- avoid relying on unverified claims about public datasets.

### 24.6 Scraping

Scraping law and contract risk varies by jurisdiction, website and method.

US case law does not provide a universal clearance for an Ireland-based commercial marketplace system.

Acquisition remains outside the PUE architecture so that providers and collection methods can change without rewriting product reasoning.

---

## 25. Observability and Developer Output

### 25.1 Case trace

Each run should produce a concise trace:

```text
Case admitted
Evidence extracted: 6
Claims supported: 4
Active hypotheses: 2
Candidates retrieved: 8
Candidates hard rejected: 6
Leading Candidate: GPU-WB-EK-4090
Decision: CLASSIFIED / PRODUCT_TYPE
Comparability: NOT_COMPARABLE_PRODUCT_FORM
Duration: 18 ms
```

### 25.2 Debug rendering

Add a human-readable renderer that prints:

- Observation;
- Evidence;
- Claims;
- hypotheses;
- Candidate comparison;
- Decision;
- Explanation.

This is a developer tool and does not require a UI.

### 25.3 Benchmark report

A benchmark command should emit:

- Markdown;
- JSON;
- optional CSV case results.

Suggested command:

```text
arb pue benchmark <dataset>
```

---

## 26. First Three Sprints

### Sprint 1 — Traceable deterministic pipeline

**Objective:** Make the complete reasoning chain run.

Deliver:

- package structure;
- enums and immutable object model;
- Observation adapter from `NormalizedListing`;
- deterministic title Evidence Extraction;
- Claim Construction and Validation;
- bounded Hypothesis Generation;
- hand-seeded 30–50-record catalogue;
- exact, structured and fuzzy Candidate Retrieval;
- rule-based Candidate Evaluation;
- Decision and Explanation;
- SQLite Reasoning Record persistence;
- 20–25 mandatory acceptance cases.

Definition of done:

- all stages run end to end;
- complete reasoning records persist;
- core harmful-form cases pass;
- no LLM, vision or vector system added.

### Sprint 2 — Product-form protection and partial identity

**Objective:** Make the first slice genuinely safer than title matching.

Deliver:

- complete product-form terminology artifact;
- hard contradiction matrix;
- compatibility-versus-identity handling;
- packaging and bundle handling;
- partial identification;
- indistinguishable-variant handling;
- explicit abstention reasons;
- Product Understanding Result publication envelope;
- shadow-mode integration with the existing pipeline;
- classifier/PUE comparison report.

Definition of done:

- no known accessory or packaging cases become complete GPUs;
- incomplete identity produces partial or classified outcomes;
- PUE and classifier differences are inspectable.

### Sprint 3 — Benchmark, replay and release gate

**Objective:** Demonstrate measurable product value.

Deliver:

- 100–150-case release benchmark;
- benchmark harness and metrics;
- replay command;
- versioned policy and catalogue releases;
- error taxonomy;
- regression suite;
- performance diagnostic;
- first ADR set;
- recommendation on whether PUE product-form output may affect downstream comparability.

Definition of done:

- release benchmark passes;
- all harmful errors are reviewed;
- Candidate recall and Decision quality are reported independently;
- replay is deterministic under the same versions;
- the project has evidence for the next capability rather than adding one speculatively.

---

## 27. Required ADRs

Create concise Architecture Decision Records for:

1. PUE placement and relationship to the existing classifier.
2. Dataclasses versus external schema library for v0.1.
3. Seed catalogue source and license status.
4. SQLite JSON persistence for the first slice.
5. Decision taxonomy and comparability semantics.
6. Uncertainty representation and rejection of one universal probability.
7. Shadow-mode release strategy.
8. Semantic deduplication position after product understanding.

Each ADR should contain:

- context;
- decision;
- alternatives;
- consequences;
- validation plan;
- conditions for reconsideration.

---

## 28. Deferred Decisions and Activation Gates

| Deferred capability | Activation evidence |
|---|---|
| Pydantic or msgspec migration | Serialization/validation is a measured bottleneck or API schemas require it |
| DuckDB or Parquet | SQLite or JSON inspection becomes a measured analytical bottleneck |
| Polars | Batch feature processing is materially limited by current implementation |
| BM25 full-text search | Token/fuzzy retrieval fails Candidate recall at catalogue scale |
| Vector retrieval | Lexical/structured methods miss semantically equivalent Candidates in benchmarked categories |
| OCR | Label or image text is frequently decision-critical and recoverable |
| Computer vision | Product form or variant errors persist where images contain decisive information |
| LLM investigation | Rule, retrieval and compact-model failures show a recurring language-reasoning gap |
| Human-review UI | Review-eligible case volume and value justify a workflow |
| Distributed queues | Local workers fail measured throughput or reliability requirements |
| Production catalogue license | Seed catalogue proves value and live coverage becomes the limiting factor |
| Calibrated probabilities | Sufficient labelled outcomes exist for calibration |
| Automatic learning | Multiple manual capability releases prove the controlled evaluation loop |

No deferred capability should be introduced merely because it appears in the broader architecture.

---

## 29. Risks and Controls

### Risk 1 — Overbuilding the architecture

**Control:** Implement only the objects and components named in this specification.

### Risk 2 — Treating the current classifier as authoritative

**Control:** Adapt classifier output into Evidence or proposed Claims.

### Risk 3 — Catalogue gaps force incorrect matches

**Control:** Permit zero Candidates, classification and abstention.

### Risk 4 — Similarity overrides product form

**Control:** Hard contradiction rules execute after retrieval and before Decision Formation.

### Risk 5 — One score is misread as probability

**Control:** Preserve retrieval score, fit dimensions and uncertainty bands separately.

### Risk 6 — Semantic deduplication occurs too early

**Control:** Keep source deduplication distinct from product-identity grouping.

### Risk 7 — Rules grow without evaluation

**Control:** Every new rule must cite benchmark cases and enter the regression suite.

### Risk 8 — External dataset claims are wrong

**Control:** Verify availability and license before import; seed locally first.

### Risk 9 — Documentation delays implementation

**Control:** This document is the implementation handoff. New documentation must solve an observed build or evaluation problem.

---

## 30. Definition of Done for PUE v0.1

PUE v0.1 is considered working when:

1. The complete reasoning chain runs for normalized GPU-domain listings.
2. Every Decision is traceable to the source Observation.
3. Material Claims identify their Evidence.
4. Multiple hypotheses are supported where ambiguity exists.
5. Candidate Retrieval is distinct from Candidate Evaluation.
6. Product-form contradictions can reject highly similar Candidates.
7. Exact, partial, classified, ambiguous and abstaining outcomes work.
8. Escalation is not confused with a Decision.
9. Explanations are faithful to the structured reasoning.
10. Complete Reasoning Records persist and replay.
11. The PUE runs in shadow mode beside the current classifier.
12. A labelled benchmark demonstrates product-form protection.
13. No known accessory or packaging benchmark case becomes a complete graphics card.
14. Unknown catalogue cases are not forced into the nearest product.
15. The first performance diagnostic completes without structural failure.
16. The implementation and benchmark identify the highest-value next capability.

At that point, the project should stop expanding v0.1 documentation and proceed through measured product improvement.

---

## 31. Immediate Implementation Checklist

Before Sprint 1 begins:

- [ ] Create the `pue` package and test directories.
- [ ] Record ADR for classifier/PUE integration.
- [ ] Implement enums and immutable dataclasses.
- [ ] Define serialization and validation helpers.
- [ ] Create `gpu-seed-0.1.0` catalogue with 30–50 records.
- [ ] Create the first 20–25 labelled acceptance cases.
- [ ] Implement `NormalizedListing → Observation` adapter.
- [ ] Add deterministic term and identifier artifacts.
- [ ] Implement the component contracts.
- [ ] Add SQLite migration for `pue_cases`.
- [ ] Add reasoning-record renderer.
- [ ] Run the first end-to-end case before adding sophistication.

---

## 32. Final Implementation Rule

The first vertical slice exists to answer one question:

> Can the Digital Arbitrage system form a traceable and measurably safer understanding of a marketplace listing than title classification and similarity matching alone?

Build the smallest system capable of answering that question.

Every additional package, model, data source, object, service or processing stage must earn its place through a measured failure of the working slice.
