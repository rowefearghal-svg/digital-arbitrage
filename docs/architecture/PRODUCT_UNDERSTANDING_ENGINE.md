# Product Understanding Engine

**Version:** 0.1 — Conceptual Manuscript, implementation-aligned
**Status:** Working document for building and evaluating the PUE
**Primary objective:** Enable a working Product Understanding Engine; further refinement should stop when it no longer improves implementation decisions.

# Chapter 1 — Problem Definition

## 1.1 Purpose

The Product Understanding Engine (PUE) is responsible for determining what a marketplace listing actually represents.

Its purpose is to transform unstructured marketplace listings into structured, explainable product understanding that downstream components of the Digital Arbitrage platform can trust.

The PUE identifies the listing independently before any commercial or search comparison is made. A user's search intent may be supplied later as comparison context, but it must not alter the factual interpretation of the listing.

The engine does not decide whether to buy an item. It determines what the listing is, what level of identity is justified, and what remains unresolved.

## 1.2 Problem Statement

Marketplace listings are highly inconsistent.

The same product may be described in hundreds of different ways, while many unrelated listings deliberately or accidentally contain the same keywords.

For example, a search for:

> RTX 4090

may return:

* a complete graphics card
* an empty retail box
* a replacement fan
* a power cable
* a repair service
* a wanted advertisement
* a bundle containing several products
* a damaged unit
* a compatible accessory
* an unrelated listing containing "4090"

A simple keyword search cannot reliably distinguish between these cases.

The Product Understanding Engine exists to solve this problem.

---

## 1.3 Primary Objective

For every marketplace listing, produce the most specific justified product-understanding Decision, together with its supporting Evidence, material contradictions, provenance, and uncertainty.

A Decision may identify an exact product, a broader family or product form, preserve several plausible alternatives, or abstain when the available information is insufficient.

The engine should produce consistent results across supported marketplaces without allowing marketplace-specific terminology or commercial attractiveness to determine product identity.

## 1.4 Design Goals

The Product Understanding Engine should be:

* Marketplace independent.
* Product-category independent.
* Explainable.
* Deterministic where possible.
* Extensible.
* Measurable.
* Testable.
* Compatible with future AI-assisted reasoning.

---

## 1.5 Non-Goals

The Product Understanding Engine does not:

* estimate resale price
* calculate profit
* calculate ROI
* estimate demand
* choose whether to purchase
* negotiate with sellers
* place orders

Those responsibilities belong to later components of the Digital Arbitrage platform.

---

## 1.6 Inputs

The engine may receive evidence from multiple sources, including:

* listing title
* listing description
* marketplace category
* product attributes
* price
* images
* seller information
* marketplace metadata
* historical observations
* future AI-derived evidence

Not every marketplace will provide every input.

The engine must operate correctly with partial information.

---

## 1.7 Outputs

For every listing, the engine should produce structured outputs that downstream systems can consume.

At a minimum, these outputs include:

- product-understanding Decision;
- product form and product type;
- identification level, such as family, model, variant, or exact known product;
- selected Candidate or unresolved alternatives, where applicable;
- supporting and contradictory Evidence;
- multidimensional uncertainty information;
- explanation of the Decision;
- provenance and capability-version references;
- unresolved Information Requirements;
- comparability guidance for downstream systems.

The PUE does not require one universal confidence score. Where numerical confidence is used, its meaning and calibration status must be explicit.

## 1.8 Core Principles

The engine should follow these principles:

1. Preserve source information before interpretation.
2. Prefer Evidence over assumptions.
3. Independent corroborating signals may strengthen a conclusion, but repeated or correlated signals must not be double-counted.
4. Strong contradictions must remain visible.
5. Every material Claim and Decision should be explainable.
6. Partial identification or abstention is preferable to an unsupported exact match.
7. AI components may propose structured Evidence, Claims, Candidates, or questions, but must not bypass validation and Decision Formation.
8. Every important failure should improve the evaluation and regression datasets.
9. Product identity must remain separate from price, profitability, and recommendation.
10. Architecture should remain generic so that new marketplaces require minimal bespoke reasoning logic.

## 1.9 Success Criteria

The Product Understanding Engine will be considered successful when it can:

- accurately identify what a listing represents at the level supported by the Evidence;
- distinguish complete products from accessories, parts, services, packaging, bundles, and compatible items;
- avoid harmful over-specific matches and abstain when required;
- retrieve the correct Candidate with high recall where that Candidate exists in available knowledge;
- preserve contradictions and explain why alternatives were accepted or rejected;
- operate consistently across multiple marketplaces and product categories;
- provide measurable performance against a labelled benchmark dataset;
- meet practical throughput and cost targets;
- improve through evaluated, versioned releases rather than uncontrolled live modification.

## 1.10 Scope

This document defines the architecture of the Product Understanding Engine.

Subsequent chapters will define:

* listing relationships
* evidence sources
* evidence signals
* decision architecture
* confidence modelling
* benchmark methodology
* implementation roadmap


# Chapter 2 — Conceptual Model

## 2.1 Purpose

The Product Understanding Engine (PUE) does not attempt to classify listings using a single label. Instead, it builds an internal representation of what it believes exists within a marketplace listing.

This representation forms the basis for all subsequent reasoning and decision making.

The objective is not to determine whether a listing should be purchased. The objective is to understand what the listing most likely represents.

---

## 2.2 Design Philosophy

The Product Understanding Engine reasons about evidence rather than assumptions.

Every conclusion produced by the engine is supported by one or more pieces of evidence and is associated with a measurable level of confidence.

The engine does not assume certainty unless supported by strong evidence.

Unknown or uncertain conclusions are considered valid outcomes.

---

## 2.3 Search Intent and Comparison Context

The core PUE reasoning process begins with the marketplace Observation, not with a desired commercial answer.

Search intent may be supplied as optional comparison context describing what the user is trying to find, such as:

- a complete product;
- a replacement component;
- an accessory;
- packaging or documentation;
- a service;
- another related entity.

This context can help the system assess relevance and comparability after it has formed an independent understanding of the listing. It must not cause the engine to reinterpret an accessory as the desired main product or otherwise force the listing to match the search.

The logical separation is:

    Listing Observation
            ↓
    Product Understanding
            ↓
    Comparison with Search Intent
            ↓
    Commercial Evaluation

This prevents the user's objective from contaminating product identity.

## 2.4 Entities

An Entity is any object or concept that may appear within a marketplace listing.

Examples include, but are not limited to:

* products
* components
* accessories
* packaging
* manuals
* services
* software licences
* bundles

The engine is designed so that new entity types can be introduced without modifying the core reasoning architecture.

---

## 2.5 Attributes

Each entity may possess one or more attributes.

Attributes describe properties of an entity and vary according to its type.

Examples include:

* manufacturer
* model
* product family
* variant
* revision
* colour
* storage capacity
* memory
* size
* condition
* quantity

The conceptual model does not require every entity to possess every attribute.

Unknown values are explicitly permitted.

---

## 2.6 Relationships

Entities may be related to one another.

Relationships describe how entities interact rather than acting as fixed classifications.

Examples include:

* exact match
* product variant
* compatible with
* replacement for
* accessory for
* bundled with
* packaging for
* contains
* alternative to

Relationships are expected to evolve as the Product Understanding Engine matures.

---

## 2.7 Evidence

Every conclusion generated by the Product Understanding Engine must be supported by evidence.

Evidence may originate from many sources, including:

* listing title
* listing description
* structured marketplace data
* product identifiers
* images
* extracted specifications
* historical observations
* future machine learning models
* future AI reasoning

Evidence may:

* support a conclusion
* contradict a conclusion
* increase confidence
* decrease confidence

The engine should retain supporting evidence whenever practical to improve explainability and future learning.

---

## 2.8 Hypotheses

The Product Understanding Engine maintains hypotheses rather than absolute truths.

A hypothesis represents the engine's current best understanding of a listing based upon all available evidence.

Hypotheses may strengthen, weaken or change entirely as additional evidence becomes available.

This allows the engine to reason under uncertainty while remaining adaptable to new information.

---

## 2.9 Uncertainty and Confidence

The PUE represents uncertainty across several distinct dimensions rather than relying on one universal confidence score.

Relevant dimensions include:

- Observation quality;
- extraction confidence;
- source reliability;
- Claim support;
- contradiction severity;
- hypothesis coherence and Evidence coverage;
- Candidate fit and distinguishability;
- Decision confidence at the stated identification level;
- calibration status.

These values answer different questions and must not be combined without preserving their original meaning.

High Decision confidence should require sufficiently strong Evidence, acceptable contradiction handling, and clear separation from competing Candidates. A broader partial identification may therefore have high confidence even when the exact variant remains unresolved.

## 2.10 Structured World Model

At the completion of processing, the Product Understanding Engine should possess a structured internal model describing what it believes exists within the listing.

Rather than producing a single label, the engine should represent:

* identified entities
* extracted attributes
* relationships between entities
* supporting evidence
* conflicting evidence
* active hypotheses
* uncertainty dimensions and any calibrated confidence estimates
* unresolved uncertainty

This structured representation becomes the foundation upon which downstream systems perform pricing, arbitrage analysis, recommendation scoring and future learning.

---

## 2.11 Future Evolution

The Product Understanding Engine is intended to reason about any product category without requiring changes to its conceptual architecture.

New marketplaces, new product categories and future reasoning technologies should extend the available evidence rather than alter the conceptual model itself.

The architecture is therefore designed to remain stable while the engine's knowledge and capabilities continue to grow.


# Chapter 3 — Evidence Model

## 3.1 Purpose

The Product Understanding Engine (PUE) reasons from evidence.

Every conclusion produced by the engine must be traceable to one or more pieces of supporting evidence.

The objective of the Evidence Model is to provide a consistent framework for collecting, representing, evaluating and combining evidence from many different sources.

The conceptual model defines *what* the engine understands.

The Evidence Model defines *why* the engine believes it.

---

## 3.2 Definition of Evidence

Evidence is any information that supports, weakens or contradicts a hypothesis.

Evidence may originate from deterministic systems, machine learning models, AI reasoning, external catalogues or future technologies.

The reasoning engine should evaluate evidence based upon its quality rather than the technology that produced it.

---

## 3.3 Sources of Evidence

Evidence may be obtained from many sources, including but not limited to:

* marketplace title
* marketplace description
* structured marketplace attributes
* product identifier observations (UPC, EAN, GTIN, ISBN, MPN, etc.)
* product images
* seller supplied specifications
* seller metadata
* marketplace category
* pricing information
* historical observations
* external product catalogues
* local machine learning models
* AI reasoning systems

The architecture should remain open to future evidence sources.

---

## 3.4 Evidence Characteristics

Every item of evidence should possess characteristics that allow it to be evaluated consistently.

Examples include:

* source
* reliability
* specificity
* completeness
* freshness
* confidence
* timestamp (where applicable)

These characteristics are independent of the evidence itself.

---

## 3.5 Evidence Strength

Not all evidence contributes equally.

Some evidence may strongly identify an entity, while other evidence may only weakly suggest a possibility.

For example:

* validated product identifier matched through a versioned Knowledge Artifact — very strong
* manufacturer part number validated in the relevant product domain — very strong
* extracted model number — strong
* image recognition — moderate to strong
* marketplace title — moderate
* description text — moderate
* category — weak
* price — weak
* unsupported seller assertion — weak

These examples are illustrative only.

The engine should be capable of evolving its assessment of evidence strength as experience and data improve.

---

## 3.6 Supporting and Conflicting Evidence

Evidence may agree or disagree.

Examples include:

* title indicates RTX 4080
* image indicates RTX 4070
* manufacturer part number identifies RTX 4070

Conflicting evidence should not cause immediate rejection.

Instead, the engine should retain the conflict and allow subsequent reasoning stages to determine the most probable explanation.

---

## 3.7 Missing Evidence

Absence of evidence should not be interpreted as evidence of absence.

Listings frequently contain incomplete information.

The engine should therefore distinguish between:

* evidence that contradicts a hypothesis
* evidence that is missing

Missing information should generally reduce confidence rather than invalidate a hypothesis.

---

## 3.8 Evidence Independence

Independent pieces of evidence provide stronger support than repeated observations of the same fact.

For example:

A manufacturer part number and a verified barcode agreeing provide stronger support than two copies of the same title.

Future reasoning components should consider evidence independence when estimating confidence.

---

## 3.9 Explainability

Every significant conclusion should be explainable.

Where practical, the engine should retain the principal evidence supporting a hypothesis.

This allows:

* debugging
* benchmarking
* model improvement
* user inspection
* future learning

The engine should never produce important conclusions that cannot be traced back to supporting evidence.

---

## 3.10 Technology Independence

The Evidence Model does not prescribe specific algorithms.

Regex, product databases, embeddings, OCR, computer vision, machine learning and large language models are all considered evidence providers.

Future technologies should integrate by contributing evidence rather than requiring changes to the conceptual architecture.

---

## 3.11 Summary

The Product Understanding Engine reasons by evaluating evidence rather than trusting any single source.

The Evidence Model provides a common language through which deterministic algorithms, machine learning models and AI systems contribute to a single reasoning process.

This separation allows the architecture to remain stable while individual technologies continue to improve.


# Chapter 4 — Product Schema, Taxonomy and Ontology

## 4.1 Purpose

The Product Understanding Engine must reason about products using a consistent internal representation rather than the inconsistent language used by marketplace listings. Sellers describe identical products in different ways, omit information, introduce errors, and use marketplace-specific terminology. Without a common schema, every reasoning task becomes ambiguous and difficult to implement.

The purpose of this chapter is to define the canonical language used by the Product Understanding Engine to represent products, their attributes, their relationships, and their organisation. This schema becomes the shared vocabulary used throughout the system, allowing evidence extraction, candidate retrieval, hypothesis generation, decision making, and learning to operate on the same underlying representation.

The schema describes real-world products, not marketplace listings. Listings are observations about products; the schema defines the products themselves.

## 4.2 Design Principles

The Product Schema must satisfy the following principles:

* The schema represents real-world products independently of any marketplace.
* Every entity must have a clearly defined semantic meaning.
* Attributes must represent objective product characteristics rather than presentation details.
* The schema must be extensible without requiring redesign of the engine.
* Category-specific schemas should inherit common concepts wherever practical.
* The schema should maximise explainability and maintainability.
* Technology choices must not influence the schema design.
* Schema evolution must preserve compatibility with previously processed data.

These principles ensure that the schema remains stable even as extraction techniques, machine learning models, and marketplaces evolve.

## 4.3 Product Types

A Product Type defines a category of products that share a common semantic meaning and attribute schema.

Examples include:

* Graphics Processing Unit (GPU)
* Central Processing Unit (CPU)
* Laptop Computer
* Smartphone
* Digital Camera
* Television
* Shoe
* Book

Each Product Type defines:

* required attributes
* optional attributes
* valid relationships
* applicable units
* variant dimensions

The Product Understanding Engine reasons about Product Types rather than attempting to memorise individual products.

## 4.4 Canonical Attributes

Every Product Type is described using Canonical Attributes.

A Canonical Attribute represents a stable property of the real-world product.

Example – GPU

| Attribute | Example |
| --- | --- |
| Manufacturer | NVIDIA |
| Model | RTX 4080 |
| Memory Capacity | 16 GB |
| Memory Type | GDDR6X |
| Interface | PCI Express 4.0 |
| Cooler Design | Triple Fan |
| Colour | Black |

Marketplace descriptions are transformed into Canonical Attributes during evidence extraction. Reasoning is performed over Canonical Attributes rather than raw listing text.

## 4.5 Attribute Types

Canonical Attributes are classified according to their data type.

Supported attribute types include:

* String
* Integer
* Decimal
* Boolean
* Enumeration
* Measurement
* Date
* List
* Reference to another entity

Each attribute type defines validation rules and comparison behaviour used throughout the engine.

## 4.6 Canonical Values and Units

Equivalent values must be normalised into a single canonical representation.

Examples include:

* 8GB
* 8192 MB
* 8 GiB

These represent the same underlying memory capacity.

Similarly:

* 2 TB
* 2000 GB
* 2048 GB

may require domain-specific interpretation depending on context.

Normalisation ensures that different textual representations do not create artificial differences during reasoning.

## 4.7 Product Families, Models and Variants

The schema distinguishes between different levels of product identity.

Example:

Graphics Card Family
        │
RTX 4080
        │
Manufacturer Variant
        │
MSI RTX 4080 Gaming X Trio
        │
Edition
        │
White Edition
        │
Individual Marketplace Listing

These represent different semantic concepts and must not be treated as interchangeable.

## 4.8 Relationship Types

Canonical entities may be connected through explicit semantic relationships.

Examples include:

* Variant Of
* Parent Of
* Child Of
* Accessory For
* Replacement Part For
* Compatible With
* Bundle Contains
* Packaging For
* Supersedes
* Discontinued By

Relationships are first-class entities within the Product Understanding Engine and may themselves carry evidence and confidence.

## 4.9 Schema Evolution

The Product Understanding Engine must evolve as new products emerge.

The schema therefore supports:

* new Product Types
* new Canonical Attributes
* new Relationship Types
* deprecated concepts
* versioned schemas

Schema evolution must preserve historical compatibility and maintain traceability of changes.

No existing data should become invalid solely because the schema has expanded.

## 4.10 Product Ontology

The Product Ontology defines how Product Types, Attributes and Relationships combine into a structured representation of product knowledge.

Example:

Product Type
    ↓
GPU
    ↓
has Manufacturer
    ↓
NVIDIA
    ↓
produces
    ↓
RTX 4080
    ↓
has Variant
    ↓
MSI Gaming X Trio
    ↓
contains
    ↓
16 GB GDDR6X

The ontology provides the semantic framework within which reasoning occurs. It enables the engine to interpret evidence, compare products, infer relationships, and maintain a consistent understanding of the product domain.

## 4.11 Summary

This chapter defines the canonical language of the Product Understanding Engine. All subsequent components—including evidence extraction, candidate retrieval, hypothesis generation, evaluation, and learning—operate upon this shared representation.

By separating the representation of products from the representation of marketplace listings, the engine establishes a stable, extensible foundation that remains independent of any individual marketplace, extraction technique, or machine learning model.


# Chapter 5 — Observation and Provenance Model

## 5.1 Introduction

Every Product Understanding Engine begins with information collected from the outside world. Marketplace listings, manufacturer catalogues, retailer feeds, auction sites, APIs and human submissions all describe products from different perspectives, with varying levels of completeness, quality and accuracy. These descriptions are frequently inconsistent, incomplete, duplicated or contradictory. Consequently, the engine cannot assume that any individual source represents objective truth.

For this reason, the Product Understanding Engine does not treat incoming information as product facts. Instead, every piece of incoming information is modelled as an Observation—an immutable record describing what a particular source claimed about a product at a specific point in time. Observations are therefore the fundamental units of information within the engine and constitute the primary source of truth from which all subsequent reasoning is derived.

Evidence, hypotheses, uncertainty assessments and canonical product representations are not stored as primary records. They are derived artefacts generated through successive stages of reasoning over collections of observations. Every conclusion reached by the engine must therefore remain traceable to the observations from which it originated, ensuring complete explainability, reproducibility and auditability.

This distinction between observations and products forms one of the foundational principles of the Product Understanding Engine architecture. Products represent the engine's current understanding of reality, whereas observations represent historical records of what external sources have claimed about that reality.


## 5.2 Observation Philosophy

### 5.2.1 Purpose

The Observation model defines how information from external sources enters the Product Understanding Engine.

Its purpose is to ensure that incoming information is:

* preserved without being mistaken for truth;
* traceable to its source;
* reproducible;
* versioned over time;
* suitable for later extraction, reasoning and review.

The Observation model forms the boundary between the external world and the internal reasoning system.

### 5.2.2 Definition

An Observation is an immutable, timestamped record of what a specific source presented or asserted at a particular point in time.

An observation may originate from:

* a marketplace listing;
* a manufacturer catalogue;
* a retailer feed;
* an auction platform;
* an API response;
* a webpage;
* a document;
* an image;
* a human submission;
* an internal system event.

An observation records what was received. It does not establish whether the information is accurate.

For example, a marketplace listing titled:

“NVIDIA RTX 4080 16GB Gaming X Trio White”

constitutes an observation that the source presented an item using that description. It does not prove that the item is genuine, complete, correctly identified or even physically present.

### 5.2.3 Architectural Role

The Observation is the primary input object of the Product Understanding Engine.

The information flow is:

External source
      ↓
Immutable Observation
      ↓
Normalisation
      ↓
Evidence and Claims
      ↓
Candidate Products
      ↓
Hypotheses
      ↓
Decision
      ↓
Canonical Product Understanding

Every downstream object must remain traceable to one or more observations.

Observations therefore form the historical foundation from which the engine constructs its current understanding of products.

### 5.2.4 Responsibilities

An Observation is responsible for preserving:

What was received

* Raw source payload
* Source fields
* Text
* Media references
* Source identifiers

Where it came from

* Source system
* Marketplace
* Connector
* Endpoint
* Retrieval method

When it was observed

* Source publication or update time, when available
* Retrieval time
* Ingestion time

How it was collected

* Collector version
* Connector version
* API version
* Request or collection context

Its relationship to other observations

* Previous version
* Later version
* Duplicate capture
* Related source record
* Replacement or correction

The Observation is not responsible for determining product identity, correctness or commercial value.

### 5.2.5 What an Observation Is Not

An Observation is not:

* a canonical product;
* an accepted fact;
* extracted evidence;
* a product hypothesis;
* a match decision;
* a universal confidence score;
* a recommendation;
* a serving or search document.

These distinctions must remain explicit throughout the architecture.

Observation versus product

A product represents an entity believed to exist in the real world.

An observation represents one source’s description of that entity—or of something that may be that entity.

One product may be represented by thousands of observations.

One observation may also describe:

* multiple products;
* a bundle;
* an accessory;
* packaging only;
* a replacement part;
* an incorrectly labelled item;
* no valid product at all.

Observation versus fact

A fact is a conclusion accepted by the engine under a defined level of confidence.

An observation merely records a source claim.

For example:

Observation:
Seller states that the item has 16 GB of memory.

Possible derived claim:
memory_capacity = 16 GB

Possible later conclusion:
The listing most likely represents an RTX 4080 16 GB variant.

The original source statement and the engine’s conclusion must remain separate.

Observation versus evidence

Evidence is an interpreted signal derived from an observation.

Examples include:

* a model number extracted from a title;
* a logo detected in an image;
* a barcode read from packaging;
* a memory capacity parsed from specifications;
* a seller-category mismatch;
* a visual similarity score.

The observation preserves the source material. Evidence records what a particular extraction process inferred from it.

### 5.2.6 Immutability

Observations must be immutable after successful ingestion.

The system must not overwrite:

* raw source fields;
* raw payloads;
* source identifiers;
* source timestamps;
* provenance metadata;
* collection context.

When a source changes, the engine creates a new observation.

Observation O1
Captured at 10:00
Title: “RTX 4080 Gaming X Trio”

Observation O2
Captured at 14:00
Title: “RTX 4080 Gaming X Trio White 16GB”

O2 does not replace or edit O1. Both remain available.

The relationship between them indicates that they represent successive observed states of the same source record.

Reasons for immutability

Immutability enables:

* reproducible decisions;
* audit trails;
* historical analysis;
* extraction replay;
* model comparison;
* debugging;
* dataset construction;
* detection of source changes;
* reconstruction of prior system states.

It also prevents later processing from silently changing the historical record.

### 5.2.7 Corrections and Invalid Observations

Immutability does not mean that incorrect records remain unqualified.

An observation may later be marked as:

* invalid;
* incomplete;
* corrupted;
* duplicated;
* withdrawn;
* superseded;
* collected in error;
* prohibited from downstream use.

These statuses are represented through separate lifecycle records, validation results or events.

The original observation remains unchanged.

For example:

Observation O17
Status event: ValidationFailed
Reason: Payload truncated during collection

The system preserves what occurred while preventing the defective observation from influencing later reasoning.

### 5.2.8 Products as Evolving Hypotheses

A canonical product record should not be treated as unchangeable truth.

It represents the engine’s current best-supported understanding of a real-world product.

That understanding may change when:

* new observations arrive;
* better evidence is extracted;
* an ontology is updated;
* a manufacturer publishes new information;
* a previous match is corrected;
* a model or rule is improved;
* human review resolves ambiguity.

The architecture therefore distinguishes between:

Historical observations
        ↓
Current evidence
        ↓
Current product hypothesis
        ↓
Current accepted representation

The accepted representation may evolve, but its supporting history must remain available.

### 5.2.9 Provenance as an Inseparable Property

An observation without provenance is incomplete.

Every observation must identify, as far as technically available:

* the source;
* the source record identifier;
* the collection mechanism;
* the collection time;
* the source time;
* the connector or collector version;
* the API or page version;
* the original payload or payload reference;
* relevant request context;
* any transformation applied before storage.

Provenance must not be added as an optional afterthought. It is part of the observation’s identity and meaning.

The statement:

“The item has 16 GB of memory”

has limited value without knowing:

* which source stated it;
* when it was stated;
* whether it appeared in a title, image or specification table;
* which parser extracted it;
* whether the source later changed.

### 5.2.10 Separation of Source Data and Interpretation

The architecture must maintain a strict boundary between:

Source layer

What the external system supplied.

Interpretation layer

What the Product Understanding Engine inferred from it.

Raw title:
“MSI 4080 Trio White 16G”

Normalised text:
“MSI RTX 4080 Gaming X Trio White 16 GB”

Extracted claims:
manufacturer = MSI
product_family = RTX 4080
variant = Gaming X Trio
colour = White
memory_capacity = 16 GB

The raw title must remain unchanged.

Normalisation and extraction outputs must identify:

* the observation they came from;
* the transformation or extractor used;
* the version of that process;
* the time the output was produced.

This allows future versions of the engine to reinterpret the same observation without modifying historical data.

### 5.2.11 Time Semantics

The system must not use a single ambiguous timestamp.

At minimum, it should distinguish:

Source event time

When the source claims the record was created, published or changed.

Observation time

When the collector actually saw or retrieved the source record.

Ingestion time

When the record entered durable Product Understanding Engine storage.

Processing time

When a downstream transformation, extraction or decision occurred.

These timestamps may differ significantly.

For example:

Source updated:       09:00
Collector retrieved:  09:17
Stored internally:    09:18
Evidence extracted:   09:23
Decision produced:    09:25

The distinction is necessary for lineage, freshness analysis and replay.

### 5.2.12 Observation Granularity

An observation should represent one coherent source record captured at one point in time.

Examples:

* one eBay listing response;
* one StockX product-market response;
* one manufacturer product page;
* one catalogue row;
* one retailer offer;
* one human-submitted product record.

Large inputs may contain multiple source records. These should normally be divided into separate observations while preserving a relationship to the parent ingestion batch.

For example:

Catalogue file
    ↓
Ingestion batch
    ├── Observation 1
    ├── Observation 2
    ├── Observation 3
    └── Observation 4

This provides precise lineage without losing batch context.

### 5.2.13 Observation Independence

Observation storage should not depend on whether the engine can currently understand the record.

An observation may be accepted even when:

* its product type is unknown;
* no candidate product can be found;
* the language is unsupported;
* images cannot yet be processed;
* required attributes are missing;
* the record conflicts with the current schema.

This allows future models, schemas and rules to reprocess historical observations.

Failure to understand an observation is not the same as failure to preserve it.

### 5.2.14 Derived Records

All processing outputs must be stored as derived records rather than modifications to the observation.

Examples include:

* validation results;
* normalised fields;
* language detection;
* extracted claims;
* image embeddings;
* text embeddings;
* candidate sets;
* hypotheses;
* decisions;
* confidence assessments;
* human review outcomes.

A derived record must identify:

* its parent observation or observations;
* the process that produced it;
* the process version;
* the creation time;
* its own status;
* any upstream dependencies.

This creates an explicit lineage graph.

Observation O1
    ├── Normalisation N1
    ├── Image Analysis I1
    ├── Claim Set C1
    └── Candidate Set R1
              ↓
        Hypothesis H1
              ↓
         Decision D1

### 5.2.15 Serving Views Are Projections

Operational views such as:

* current listing state;
* current product page;
* search index;
* price history;
* latest seller offer;
* active arbitrage opportunity;

must be treated as projections.

A projection is a derived, rebuildable view optimised for a particular use case.

It is not the authoritative historical record.

For example, the “latest listing” table may show only the most recent active observation. If that table is deleted or corrupted, it should be reconstructable from immutable observations and lifecycle events.

### 5.2.16 Core Constraints

The following constraints are mandatory:

* Every observation has a globally unique internal identifier.
* Every observation records its source.
* Every observation records an observation or retrieval time.
* Raw source content is preserved or referenced durably.
* Stored observations are immutable.
* Source changes create new observations.
* Derived records do not modify observations.
* Every derived record references its upstream inputs.
* Invalid observations are retained with explicit status.
* Current-state views are rebuildable projections.
* An observation may exist without an identified canonical product.
* An observation must not be promoted directly to product truth without evidence evaluation.

### 5.2.17 Design Decision

The Product Understanding Engine adopts an observation-first architecture.

The system stores what sources claimed before deciding what those claims mean.

This decision intentionally prioritises:

* traceability over convenience;
* history over destructive updates;
* reproducibility over opaque state;
* evidence-based reasoning over direct field copying;
* future reinterpretation over immediate certainty.

The central principle is:

The engine must preserve reality as observed before attempting to interpret it.


## 5.3 Observation Object Model

### 5.3.1 Purpose

The Observation Object Model defines the canonical structure of an Observation within the Product Understanding Engine.

It specifies the information that every Observation must contain, how that information is organised, and the architectural constraints governing its lifecycle.

This section does not prescribe implementation technologies or storage mechanisms. Instead, it defines the logical model that all implementations must satisfy.

The Observation Object Model serves as the contract between the ingestion layer and every downstream reasoning component.

### 5.3.2 Design Goals

The Observation Object Model has six primary goals.

Goal 1 — Preserve Reality

The engine must preserve exactly what was observed without modification.

The Observation must represent the external world's description of a product rather than the engine's interpretation of it.

Goal 2 — Complete Traceability

Every downstream object generated by the Product Understanding Engine must be traceable back to one or more Observations.

No reasoning process may produce information whose origin cannot be identified.

Goal 3 — Technology Independence

The Observation model must remain independent of:

* programming language
* database technology
* storage engine
* message queue
* cloud provider

The architecture defines the logical object rather than its physical representation.

Goal 4 — Extensibility

Future versions of the engine should be able to introduce:

* additional metadata
* new artifact types
* new provenance fields
* richer relationship models

without invalidating previously stored observations.

Goal 5 — Replayability

Historical Observations must contain sufficient information to allow future versions of the engine to:

* rerun extraction
* rerun reasoning
* compare model versions
* reconstruct historical system state

without recollecting the original source.

Goal 6 — Explainability

Every decision produced by the Product Understanding Engine should be explainable through a chain of linked objects beginning with one or more Observations.

### 5.3.3 Canonical Observation Structure

Every Observation consists of seven logical components.

Observation
│
├── Identity
│
├── Raw Observation
│
├── Metadata
│
├── Provenance
│
├── Attached Artifacts
│
├── Relationships
│
└── Lifecycle Information

Each component has a distinct architectural responsibility.

### 5.3.4 Identity Component

The Identity Component uniquely identifies the Observation within the Product Understanding Engine.

It should contain information sufficient to distinguish the Observation from every other Observation regardless of source or storage implementation.

The Identity Component should include:

* Observation Identifier
* Source Identifier
* External Record Identifier (when available)
* Collection Batch Identifier (optional)
* Parent Observation Identifier (where applicable)

**Responsibilities**

The Identity Component is responsible for:

* global uniqueness
* internal referencing
* lineage construction
* relationship mapping
* audit support

Constraints

Identity values are immutable.
Internal identifiers must never be reused.
External identifiers may change independently of internal identifiers.
Identity must remain stable throughout the Observation lifecycle.

### 5.3.5 Raw Observation Component

The Raw Observation Component preserves the original information supplied by the external source.

Typical contents include:

* raw JSON payloads
* raw HTML
* XML documents
* CSV rows
* API responses
* original text
* structured attributes
* marketplace identifiers
* URLs

The engine should preserve the original representation wherever practical.

No downstream processing may overwrite this component.

### 5.3.6 Metadata Component

Metadata describes the Observation itself rather than the product.

Examples include:

* marketplace
* source system
* language
* country
* currency
* collection method
* content type
* source category
* observation size
* encoding

Metadata enables routing, filtering, localisation and processing decisions.

Metadata is descriptive and should not contain inferred product knowledge.

### 5.3.7 Provenance Component

The Provenance Component records how the Observation entered the Product Understanding Engine.

It provides the historical context required for replay, auditing and reproducibility.

Typical provenance information includes:

* collector version
* connector version
* parser version
* API version
* request method
* authentication method
* retrieval timestamp
* source timestamp
* ingestion timestamp
* pipeline identifier

Every Observation must contain sufficient provenance information to explain how it was acquired.

### 5.3.8 Attached Artifact Component

Many Observations contain associated resources that cannot be represented as simple text or structured attributes.

Artifacts may include:

* photographs
* manufacturer images
* diagrams
* PDFs
* videos
* specification sheets
* OCR outputs
* binary files

Artifacts are part of the Observation but remain distinct from the raw payload.

They are inputs for later extraction processes rather than extracted evidence themselves.

### 5.3.9 Relationship Component

Observations rarely exist in isolation.

Relationships allow the engine to model how Observations connect to one another.

Examples include:

Observation A

├── Previous Version

├── Next Version

├── Duplicate Of

├── Same Source Record

├── Same Batch

├── Derived Collection

└── Related Observation

Relationships describe structural associations only.

They do not imply semantic agreement.

For example, two Observations may describe the same marketplace listing while containing conflicting information.

### 5.3.10 Lifecycle Component

Every Observation has a lifecycle independent of the product it may describe.

Typical lifecycle stages include:

Collected

↓

Validated

↓

Stored

↓

Available for Processing

↓

Archived

Lifecycle information records the Observation's state within the Product Understanding Engine.

It does not modify the Observation's content.

### 5.3.11 Architectural Constraints

The following constraints apply to every Observation:

* Every Observation has exactly one internal identity.
* Every Observation has one originating source.
* Every Observation records when it was observed.
* Every Observation preserves its raw representation.
* Every Observation includes provenance information.
* Every Observation may contain zero or more artifacts.
* Every Observation may participate in zero or more relationships.
* Observation content is immutable after successful ingestion.
* Corrections produce new records rather than modifying existing Observations.
* Downstream components consume Observations but do not alter them.

### 5.3.12 Implementation Considerations

This section intentionally avoids prescribing implementation technologies.

A compliant implementation may use:

* relational databases,
* document databases,
* object stores,
* event logs,
* distributed storage,
* cloud-native services,
* or hybrid architectures,

provided that the logical behaviour defined by this section is preserved.

For example, an implementation may store images in object storage, metadata in PostgreSQL, and events in Kafka. Another implementation may choose a document database with embedded metadata. Both satisfy the specification if they preserve immutability, provenance, identity, and traceability.

## 5.4 Observation Identity and Versioning

### 5.4.1 Purpose

The Observation Identity and Versioning specification defines how Observations are uniquely identified, how successive observations of the same external record are represented, and how historical continuity is maintained throughout the Product Understanding Engine.

Its purpose is to ensure that:

* every Observation can be uniquely referenced;
* the history of a source record is preserved;
* source changes are represented without data loss;
* observations can be replayed in chronological order;
* downstream reasoning remains reproducible.

Identity and versioning are foundational to provenance, auditing, replay, and historical analysis.

### 5.4.2 Design Principles

The Product Understanding Engine adopts the following principles:

Identity is permanent

Once assigned, an Observation's internal identity never changes.

Identity is independent of source systems

Internal identifiers must not depend on:

* marketplace identifiers;
* URLs;
* filenames;
* API endpoints;
* database keys from external systems.

External systems may change.

Internal identity must remain stable.

Versioning preserves history

Changes to external data create new Observations.

Historical Observations are never overwritten.

History is valuable

Previous Observations remain part of the permanent knowledge base.

Historical data enables:

* replay,
* debugging,
* model evaluation,
* trend analysis,
* auditing,
* ML training.

### 5.4.3 Internal Observation Identity

Every Observation must possess a globally unique internal identifier.

This identifier represents the Observation itself—not the product, listing or source record.

Example:

Observation ID:
OBS-01J5K9Q2XH8M7V4A1P6

The specification deliberately avoids prescribing a particular identifier technology (UUID, ULID, Snowflake, etc.). The implementation must simply guarantee:

* global uniqueness,
* immutability,
* stable referencing,
* efficient lookup.

Constraints

The internal Observation ID:

* never changes;
* is never reused;
* has no semantic meaning;
* does not encode marketplace information;
* survives migrations between storage systems.

### 5.4.4 External Identity

Many sources provide their own identifiers.

Examples:

* eBay Listing ID
* StockX Product ID
* Amazon ASIN
* Manufacturer SKU
* GTIN
* EAN
* UPC

These identifiers remain valuable but are treated as external identities, not primary identities.

External identifiers:

* may change;
* may be reused by the source;
* may disappear;
* may be duplicated across systems;
* may be absent entirely.

The Product Understanding Engine therefore stores them as attributes of the Observation rather than using them as its internal identity.

### 5.4.5 Observation Series

Multiple Observations may describe the evolution of a single external record over time.

These related Observations form an Observation Series.

Example:

eBay Listing 12345

↓

Observation O1

↓

Observation O2

↓

Observation O3

↓

Observation O4

Each Observation captures the state of the listing at a specific moment.

The Observation Series represents the complete known history of that listing.

### 5.4.6 Version Creation

A new Observation version should be created whenever the engine detects a meaningful change in the observed source record.

Typical triggers include:

* title changes;
* description changes;
* price changes;
* availability changes;
* images added or removed;
* specifications updated;
* seller changes;
* condition changes;
* shipping changes;
* category changes.

The precise definition of "meaningful change" may vary by source and implementation, but the architectural principle remains:

A new observed state is represented by a new Observation.

### 5.4.7 Observation Relationships

Successive Observations should be linked to preserve continuity.

Example:

Observation O3

Previous Version → O2

Next Version → O4

This relationship enables efficient traversal of an Observation's history while preserving immutability.

Relationships describe temporal succession only.

They do not imply correctness or semantic agreement.

### 5.4.8 Deleted and Disappearing Records

External records may disappear for many reasons:

* listing sold;
* listing withdrawn;
* API no longer exposes it;
* seller deleted it;
* marketplace removed it;
* temporary outage.

The absence of a source record must not result in deletion of existing Observations.

Instead, the engine records a lifecycle event indicating that the source record is no longer observable.

Historical Observations remain intact.

### 5.4.9 Forking Histories

In rare cases, a single source record may diverge into multiple logical histories.

Examples include:

* merged listings;
* split catalogue entries;
* reused identifiers;
* marketplace migration;
* source correction.

The architecture should permit an Observation Series to branch when necessary, while preserving lineage and provenance.

Such branching should be explicit and recorded through relationships rather than by rewriting history.

### 5.4.10 Identity Across Multiple Sources

Different marketplaces often describe the same real-world product.

For example:

eBay Listing

↓

Observation A

StockX Product

↓

Observation B

Amazon Offer

↓

Observation C

Although these Observations may ultimately contribute to the same Canonical Product, they retain distinct identities.

Observation identity represents where and when information was observed, not what product the engine believes it describes.

This distinction prevents the accidental merging of historical records from independent sources.

### 5.4.11 Version Numbering

Version numbering, where used, should represent the sequence of Observations within an Observation Series.

For example:

Observation Series:
Version 1
Version 2
Version 3
Version 4

Version numbers are local to an Observation Series and have no meaning outside that context.

An implementation may derive versions from timestamps, sequence numbers, or explicit revision counters, provided chronological order can be reconstructed.

### 5.4.12 Identity and Replay

Stable identities enable the engine to replay historical processing.

For example:

Observation O17

↓

Normalisation V1

↓

Evidence Extraction V2

↓

Candidate Retrieval V3

↓

Decision V4

Years later, the same Observation can be reprocessed using newer models:

Observation O17

↓

Normalisation V5

↓

Evidence Extraction V8

↓

Candidate Retrieval V9

↓

Decision V10

The Observation remains unchanged, allowing direct comparison between historical and current reasoning.

### 5.4.13 Architectural Constraints

The following constraints are mandatory:

* Every Observation has one immutable internal identity.
* External identifiers never replace internal identity.
* Source changes create new Observations rather than modifying existing ones.
* Historical Observations are never deleted solely because the source changes.
* Observation history remains traversable.
* Observation identity is independent of Canonical Product identity.
* Multiple Observations may contribute to one Canonical Product.
* One Observation may later be determined to describe multiple products (for example, bundles or composite listings).
* Versioning preserves chronology without rewriting history.
* Identity must support replay, auditing and reproducibility.

### 5.4.14 Implementation Considerations

The architecture intentionally leaves identifier generation technology unspecified.

Implementations may choose UUIDs, ULIDs, Snowflake-style IDs, or another globally unique mechanism based on scalability and operational requirements.

Likewise, the mechanism used to detect when a new Observation version should be created is implementation-specific. Some systems may compare hashes of raw payloads, others may perform field-level diffs or rely on source-provided revision identifiers. Regardless of the approach, the observable behaviour defined by this section must remain the same: historical observations are preserved, new observed states produce new observations, and identity remains stable.

## 5.5 Provenance Model

### 5.5.1 Purpose

The Provenance Model defines how the Product Understanding Engine records the origin, lineage and processing history of every Observation and every derived object.

Its purpose is to ensure that all information within the engine can be traced back to its original source, the processes that acted upon it, and the decisions that were subsequently made from it.

Provenance provides the foundation for explainability, reproducibility, auditing, replay and continual learning.

### 5.5.2 Definition

Provenance is the complete record of where information originated, how it entered the Product Understanding Engine, how it has been transformed, and how it contributed to later reasoning.

Provenance is not optional metadata. It is a first-class architectural object that accompanies every Observation and every derived record throughout its lifecycle.

### 5.5.3 Design Principles

The Product Understanding Engine adopts the following principles:

* Every Observation has provenance.
* Every derived object has provenance.
* Provenance is immutable.
* Provenance is cumulative; each processing stage extends the provenance chain rather than replacing it.
* Every architectural decision must be reproducible from recorded provenance.
* Provenance must survive replay, reprocessing and model upgrades.

### 5.5.4 Levels of Provenance

The architecture distinguishes four complementary levels of provenance.

Source Provenance

Describes where the information originated.

Examples include:

* eBay
* StockX
* Manufacturer catalogue
* Retailer feed
* User submission

Collection Provenance

Describes how the Observation entered the Product Understanding Engine.

Examples include:

* REST API
* GraphQL
* Web crawler
* File import
* Manual entry

Collection provenance may also include connector versions, authentication method and retrieval context.

Processing Provenance

Records the processes that produced derived objects.

Typical examples include:

* collector version
* parser version
* normaliser version
* extraction model version
* reasoning model version

Every derived object records the process responsible for creating it.

Decision Provenance

Records how conclusions were reached.

Decision provenance identifies:

* supporting Observations
* supporting Evidence
* supporting Claims
* Candidate Products considered
* Hypotheses evaluated
* Decision process
* Decision version

Decision provenance enables complete explanation of every Canonical Product update.

### 5.5.5 Provenance Components

At a minimum, provenance should record:

* source system
* collection method
* retrieval context
* relevant timestamps
* processing component
* processing version
* parent objects
* upstream dependencies

These components collectively describe the complete lineage of an object.

### 5.5.6 Provenance Chain

Every derived object extends the provenance of its parent.

Observation O17
        │
        ▼
Normalisation N4
        │
        ▼
Evidence E12
        │
        ▼
Claim C6
        │
        ▼
Hypothesis H2
        │
        ▼
Decision D1

At every stage, the engine must be able to determine:

* what produced the object;
* which inputs were used;
* which process version was responsible;
* which upstream objects influenced the result.

This forms the complete lineage graph of the reasoning process.

### 5.5.7 Provenance Granularity

Provenance should be recorded at the level of the architectural object that produced the information.

For example:

* an Observation records its collection provenance;
* an extracted Claim records the extractor and model version that produced it;
* an image embedding records the vision model responsible for its generation;
* a Decision records the reasoning process and supporting evidence.

The architecture does not require every individual field to maintain separate provenance, but it must permit finer-grained provenance where future implementations require it.

### 5.5.8 Provenance Queries

The Provenance Model must support questions such as:

* Which Observation produced this Claim?
* Which model extracted this attribute?
* Which Observations support this Decision?
* Why was this product matched?
* Which version of the reasoning engine produced this result?
* Can this decision be reproduced?

The ability to answer these questions is considered a core architectural requirement.

### 5.5.9 Architectural Constraints

The following constraints apply:

* Every Observation has provenance.
* Every derived record has provenance.
* Provenance is immutable.
* Provenance must never be discarded during processing.
* Derived records reference their parent objects.
* Every decision must be traceable to one or more Observations.
* Provenance survives replay and reprocessing.
* Provenance remains independent of implementation technology.

### 5.5.10 Implementation Considerations

This section does not prescribe how provenance is stored.

Implementations may represent provenance using relational references, event logs, graph relationships, document structures or other suitable mechanisms, provided the complete lineage of every object can be reconstructed.

The architecture defines the logical provenance model rather than its physical storage.

---

## 5.6 Observation Lifecycle

### 5.6.1 Purpose

The Observation Lifecycle defines the valid states through which an Observation progresses after entering the Product Understanding Engine.

Its purpose is to provide a consistent framework for managing Observations throughout their operational life while preserving their immutability.

The lifecycle describes the status of an Observation within the engine; it does not alter the Observation itself.

### 5.6.2 Design Principles

The Observation Lifecycle is governed by the following principles:

* Every Observation has a lifecycle.
* Lifecycle state is independent of Observation content.
* Lifecycle transitions do not modify the Observation.
* Lifecycle history should be preserved.
* An Observation may be reprocessed without changing its identity.

### 5.6.3 Lifecycle States

An Observation typically progresses through the following states:

```
Collected
      │
      ▼
Validated
      │
      ▼
Stored
      │
      ▼
Available for Processing
      │
      ▼
Processing
      │
      ▼
Processed
      │
      ▼
Archived
```

The architecture defines these as logical states. Implementations may introduce additional internal states provided they remain consistent with this lifecycle.

### 5.6.4 State Descriptions

### Collected

The Observation has been successfully obtained from an external source.

### Validated

Basic validation has confirmed that the Observation is structurally suitable for storage.

Validation concerns the integrity of the Observation rather than the correctness of the product information it contains.

### Stored

The Observation has been durably persisted within the Product Understanding Engine.

At this point the Observation becomes immutable.

### Available for Processing

The Observation is eligible for downstream processing such as normalisation, extraction and reasoning.

### Processing

One or more downstream components are currently producing derived records from the Observation.

Processing does not modify the Observation itself.

### Processed

The Observation has completed the currently scheduled processing activities.

Future processing remains possible as new models, rules or capabilities become available.

### Archived

The Observation is no longer part of active operational workflows but remains available for audit, replay and historical analysis.

Archiving does not imply deletion.

### 5.6.5 Exceptional States

An Observation may also enter exceptional states, including:

* Validation Failed
* Corrupted
* Duplicate
* Quarantined
* Processing Failed

These states indicate operational conditions rather than changes to the Observation itself.

Where possible, the reason for entering an exceptional state should be recorded.

### 5.6.6 Lifecycle Transitions

Lifecycle transitions should be explicit and recorded.

For example:

```
Collected
      │
      ▼
Validated
      │
      ▼
Stored
```

rather than silently changing state.

Recording lifecycle transitions supports auditing, monitoring and operational diagnostics.

### 5.6.7 Replay and Reprocessing

Completion of the lifecycle does not prevent future processing.

An archived Observation may be reprocessed using:

* improved extraction models;
* updated ontologies;
* revised reasoning engines;
* new product types;
* enhanced image analysis.

Reprocessing generates new derived records while preserving the original Observation and its lifecycle history.

### 5.6.8 Architectural Constraints

The following constraints apply:

* Every Observation has one current lifecycle state.
* Lifecycle state does not modify Observation content.
* Lifecycle transitions are recorded.
* Observations remain immutable throughout their lifecycle.
* Archived Observations remain available for replay.
* Reprocessing creates new derived records rather than modifying existing ones.

### 5.6.9 Implementation Considerations

The architecture defines the logical lifecycle only.

Implementations may realise lifecycle management using state machines, workflow engines, event-driven architectures or other suitable approaches, provided lifecycle transitions remain explicit and historical information is preserved.

---

## 5.7 Observation Relationships

### 5.7.1 Purpose

The Observation Relationships specification defines how Observations are connected to other architectural objects within the Product Understanding Engine.

Its purpose is to preserve lineage, support reasoning, and establish the structural relationships required for traceability throughout the engine.

Relationships describe how objects are connected. They do not imply that the connected objects are correct, equivalent or semantically identical.

### 5.7.2 Design Principles

The Product Understanding Engine adopts the following principles:

* Every relationship has an explicit meaning.
* Relationships are directional unless explicitly defined as bidirectional.
* Relationships are immutable once recorded.
* Relationships preserve lineage rather than replace it.
* Multiple relationship types may exist between the same objects.

### 5.7.3 Observation Relationships

An Observation may participate in relationships with other Observations.

Typical relationships include:

* Previous Version
* Next Version
* Duplicate Of
* Same Source Record
* Same Collection Batch
* Related Observation

These relationships describe the history and organisation of Observations rather than the products they may represent.

### 5.7.4 Relationships to Derived Objects

An Observation serves as the parent of all information derived directly from it.

Typical derived relationships include:

```
Observation
    ├── produces → Normalisation
    ├── produces → Evidence
    ├── produces → Claims
    ├── produces → Image Analysis
    ├── produces → Embeddings
    └── produces → Validation Results
```

Derived objects must retain a reference to the Observation from which they originated.

### 5.7.5 Relationships to Artifacts

An Observation may reference one or more attached Artifacts.

Examples include:

* Images
* PDFs
* Videos
* Specification Sheets
* OCR Outputs
* Binary Attachments

Artifacts remain part of the Observation but are independent architectural objects that may participate in later processing.

### 5.7.6 Relationships to Canonical Products

Observations do not directly own Canonical Products.

Instead, Observations contribute evidence that may support one or more Canonical Products.

For example:

```
Observation A
          │
          ▼
      Evidence
          │
          ▼
      Hypothesis
          │
          ▼
Canonical Product
```

This separation prevents the engine from treating a single Observation as product truth.

### 5.7.7 Many-to-Many Relationships

The architecture permits many-to-many relationships where appropriate.

Examples include:

* One Observation contributing to multiple Candidate Products.
* Multiple Observations supporting one Canonical Product.
* One Observation producing multiple Claims.
* Multiple Claims supporting one Decision.

This flexibility reflects the ambiguity commonly encountered in real-world product data.

### 5.7.8 Relationship Integrity

Every relationship should satisfy the following requirements:

* Both referenced objects exist.
* The relationship type is explicitly defined.
* The direction of the relationship is unambiguous.
* Relationships do not introduce circular lineage.
* Relationship creation preserves existing history.

Invalid or broken relationships should be detected through validation rather than silently ignored.

### 5.7.9 Architectural Constraints

The following constraints apply:

* Every relationship has a defined type.
* Relationships preserve historical lineage.
* Relationships do not modify the connected objects.
* Observations may participate in multiple relationships simultaneously.
* Derived objects reference their parent Observations.
* Canonical Products are linked through reasoning rather than direct ownership.

### 5.7.10 Implementation Considerations

The architecture defines logical relationships only.

Implementations may represent relationships using foreign keys, graph edges, document references, event links or other suitable mechanisms, provided relationship semantics remain explicit and lineage is preserved.

---

## 5.8 Observation Design Patterns

### 5.8.1 Purpose

This section defines the architectural design patterns that govern the Observation subsystem of the Product Understanding Engine.

Where previous specifications define the structure and behaviour of Observations, these design patterns define the principles that should guide future architectural decisions.

The intent is to ensure that new functionality remains consistent with the core philosophy of the Product Understanding Engine, regardless of future technologies, models or implementation details.

### 5.8.2 Pattern 1 — Preserve Before Interpret

Incoming information should always be preserved before any attempt is made to interpret or transform it.

The original Observation represents the engine's record of what was received from an external source. This record forms the foundation for all subsequent reasoning and must remain intact.

Interpretation should always create new derived objects rather than modifying the original Observation.

### 5.8.3 Pattern 2 — Derive, Never Modify

Knowledge within the Product Understanding Engine evolves through derivation rather than modification.

Every stage of processing should produce new architectural objects that reference their predecessors.

This approach preserves complete historical lineage while allowing the engine's understanding of a product to evolve over time.

### 5.8.4 Pattern 3 — Separate Data from Meaning

An Observation records what an external source claimed.

It does not determine what is true.

Semantic meaning is produced through evidence generation, reasoning and decision making.

Maintaining this separation prevents raw marketplace data from being mistaken for verified product knowledge.

### 5.8.5 Pattern 4 — Relationships Over Duplication

Architectural objects should be connected through explicit relationships rather than duplicated information.

Where one object depends upon another, the dependency should be represented by a relationship rather than by copying data.

This reduces inconsistency, preserves lineage and simplifies future processing.

### 5.8.6 Pattern 5 — Provenance Everywhere

Every architectural object should retain sufficient provenance to explain how it was produced.

Provenance should accompany every stage of processing, allowing the complete reasoning process to be reconstructed from the original Observation to the final Decision.

The ability to explain a result is considered as important as the result itself.

### 5.8.7 Pattern 6 — Design for Replay

The architecture assumes that future processing models will improve.

Observations should therefore remain suitable for replay using improved extraction models, reasoning engines or ontologies without requiring recollection from external sources.

Replay is a core capability rather than an exceptional operation.

### 5.8.8 Pattern 7 — Preserve History

Historical information should never be overwritten.

When new information becomes available, the engine extends its knowledge by creating new objects and new relationships while preserving the complete historical record.

History represents the evolution of understanding and therefore forms part of the engine's knowledge base.

### 5.8.9 Pattern 8 — Explain Every Decision

Every Decision produced by the Product Understanding Engine should be explainable.

Given any Canonical Product or Decision, it should be possible to identify:

* the supporting Observations;
* the Evidence generated;
* the Claims evaluated;
* the reasoning process applied; and
* the decision that produced the current result.

Architectural features that reduce explainability should be avoided unless there is a compelling justification.

### 5.8.10 Pattern 9 — Technology Independence

The architecture defines logical concepts rather than implementation technologies.

No design pattern within this section assumes a particular database, programming language, messaging framework or machine learning platform.

Implementations may evolve over time provided they continue to satisfy the architectural principles defined within this chapter.

### 5.8.11 Summary

These design patterns collectively define the philosophy of the Observation subsystem.

They provide a consistent framework for future development by ensuring that new architectural components preserve immutability, provenance, traceability and explainability while remaining independent of specific implementation technologies.

Future extensions to the Product Understanding Engine should be evaluated against these patterns to ensure that they remain aligned with the architectural principles established throughout this section.

---

## 5.9 Chapter Summary

### 5.9.1 Purpose

This chapter has established the Observation as the foundational architectural object within the Product Understanding Engine.

Rather than treating external marketplace information as verified product knowledge, the architecture records every external interaction as an immutable Observation from which all subsequent understanding is derived.

This approach separates the collection of information from its interpretation, allowing the engine to reason about products while preserving a complete historical record of the information on which those decisions were based.

### 5.9.2 Architectural Outcomes

The Observation architecture establishes the following core capabilities:

* Immutable recording of external information.
* Complete provenance and lineage for every architectural object.
* Separation of raw observations from semantic interpretation.
* Replay and reprocessing using future models.
* Explainable reasoning through traceable relationships.
* Preservation of historical knowledge without overwriting previous understanding.

Collectively, these capabilities provide the foundation upon which the remaining Product Understanding Engine is constructed.

### 5.9.3 Relationship to Subsequent Chapters

The Observation subsystem represents the entry point of information into the Product Understanding Engine.

Subsequent chapters build upon this foundation by defining how Observations are transformed into progressively richer representations of product knowledge through evidence generation, claim extraction, candidate identification, hypothesis formation, reasoning and canonical product creation.

Throughout these later stages, the architectural principles established in this chapter continue to apply. Every derived object ultimately traces its lineage back to one or more Observations.

### 5.9.4 Key Principles

The architecture established throughout this chapter may be summarised by the following principles:

* Preserve reality before interpretation.
* Record information rather than assumptions.
* Derive knowledge rather than modify history.
* Maintain provenance throughout processing.
* Explain every architectural decision.
* Design for continual improvement through replay and reprocessing.

These principles define the philosophy of the Observation subsystem and provide the foundation for future evolution of the Product Understanding Engine.

### 5.9.5 Conclusion

The Observation subsystem forms the architectural foundation of the Product Understanding Engine.

By treating Observations as immutable records of external information and separating them from the reasoning processes that generate product knowledge, the architecture provides a robust basis for explainability, reproducibility, extensibility and continual learning.

All subsequent architectural components described within this section ultimately depend upon the Observation model established in this chapter.

# Chapter 6 — Extraction, Evidence & Claims

## 6.1 Introduction

The Product Understanding Engine does not reason directly over raw marketplace data. Instead, it transforms external information through progressively richer representations that separate source material, extraction, interpretation, and Decision Formation.

Every listing enters as an Observation: an immutable representation of information obtained from a marketplace API, webpage, image, specification sheet, document, or other source. Observations preserve the source material and remain the permanent record from which later understanding is derived.

Specialised extraction processes analyse each Observation and normally record potentially useful findings as Evidence. Some deterministic, machine-learning, or generative components may also propose structured Claims when that is the most practical interface. Proposed Claims are not authoritative: they must identify their supporting Evidence and pass through Claim Validation before they can influence a Decision.

Claim Construction and Validation organise the available Evidence into machine-readable assertions about attributes such as manufacturer, model, capacity, colour, condition, product form, or compatibility. Every accepted Claim retains explicit references to the Evidence from which it was derived.

This layered architecture allows deterministic parsers, computer vision, optical character recognition, compact classifiers, language models, and rule-based systems to coexist without allowing any one component to publish the final product identity directly.

The resulting architecture preserves provenance, supports conflicting Evidence, permits component replacement, and keeps the final Decision within the shared reasoning process.

## 6.2 Extraction Philosophy

The Product Understanding Engine is founded on a strict separation between information extraction and reasoning. This separation ensures that every stage of the pipeline has a single responsibility, making the system easier to understand, test, extend, and audit.

Extraction is responsible for discovering everything that may be useful. Reasoning is responsible for deciding what those discoveries actually mean.

The following principles govern every extraction process within the engine.

### 6.2.1 Observations Are Immutable

An Observation represents a permanent snapshot of information obtained from an external source.

Once created, an Observation is never modified by downstream components.

If additional information becomes available, a new Observation is created rather than altering an existing one.

This immutability guarantees reproducibility. Any future decision can always be traced back to the exact marketplace listing that originally produced it.

### 6.2.2 Extractors Never Modify Observations

Extraction processes operate as read-only consumers of Observations.

Their purpose is to analyse the Observation and identify potentially useful information.

They do not rewrite text, alter images, remove fields, or correct source data.

Instead, every interpretation is recorded separately as Evidence.

This preserves the integrity of the original source while allowing multiple independent interpretations to coexist.

### 6.2.3 Extractors Produce Evidence or Structured Proposals

Extraction processes normally produce Evidence describing what was detected and where it was found.

For example, an OCR extractor may detect:

    RTX 4090

A computer vision model may detect:

    Founders Edition-style cooler

A metadata parser may record:

    Marketplace category = Graphics Cards

A component may also return a proposed structured Claim, such as `product_form = accessory`, when doing so is operationally useful. The proposal must remain marked as proposed, cite its Evidence, and pass through Claim Validation.

No extractor or model may independently publish the authoritative product Decision.

### 6.2.4 Extractors Do Not Publish Authoritative Claims

Claims represent structured assertions about the product, for example:

    Manufacturer = NVIDIA
    Product Family = GeForce RTX
    Model = RTX 4090
    Product Form = Complete Product

A deterministic parser, classifier, vision-language model, or language model may propose such a Claim. However, the proposal becomes part of the shared reasoning state only after validation considers its Evidence, provenance, limitations, conflicts, and capability version.

This rule preserves a stable boundary:

    Extractor or model
            ↓
    Evidence and/or proposed Claim
            ↓
    Claim Validation
            ↓
    Accepted, contradicted, qualified, or rejected Claim

The boundary allows extraction technologies to improve without letting package-specific or model-specific output bypass the architecture.

### 6.2.5 Multiple Independent Extractors

Every Observation may be analysed by many specialised extraction processes.

Examples include:

OCR
Image classification
Logo detection
Barcode recognition
Object detection
Vision-language models
Rule-based parsers
LLM-based text extraction
Metadata parsers
Marketplace-specific extractors

These processes operate independently.

They do not communicate with one another and do not depend on one another's outputs.

Each contributes Evidence and, where permitted, clearly marked proposed Claims to the shared reasoning state.

This parallel architecture improves robustness because different extractors often detect complementary information.

### 6.2.6 Extraction Maximises Recall

During extraction, the primary objective is to avoid losing potentially valuable information.

Extractors are intentionally encouraged to produce all plausible Evidence, even when some of that Evidence may later prove to be incorrect.

False positives are acceptable at this stage because they can be filtered during reasoning.

False negatives are significantly more costly because information that is never extracted can never be recovered.

The extraction layer therefore prioritises completeness over certainty.

### 6.2.7 Reasoning Occurs Downstream

Conflict resolution, ambiguity handling, confidence aggregation, and product identification are not extraction responsibilities.

Instead, these tasks are performed during Claim Construction and Candidate Evaluation.

For example:

Evidence may simultaneously indicate:

"RTX 4090"
"RTX 4080"

Both pieces of Evidence are retained.

Neither is discarded during extraction.

The reasoning stages later determine which interpretation is better supported by the complete body of Evidence.

This separation enables the engine to explain not only its final decision but also why competing interpretations were rejected.

### 6.2.8 Benefits of the Philosophy

This architectural philosophy provides several important advantages:

Deterministic behaviour, because extraction does not depend on downstream decisions.
Explainability, since every Claim can be traced to supporting Evidence and the originating Observation.
Extensibility, allowing new extraction technologies to be added without redesigning the reasoning engine.
Parallelism, as multiple extractors can analyse the same Observation simultaneously.
Reproducibility, because immutable Observations preserve the original marketplace data.
Auditability, enabling every decision to be reconstructed from its complete evidence trail.
Future-proofing, allowing advances in OCR, computer vision, or language models to be incorporated without changing the core architecture.

## 6.3 Extraction Pipeline

The extraction pipeline defines the sequence by which raw marketplace data is transformed into structured Evidence. Rather than relying on a single monolithic extraction process, the Product Understanding Engine employs a modular pipeline composed of specialised extraction stages, each responsible for identifying a particular class of information.

This architecture enables multiple extraction technologies—including rule-based parsers, machine learning models, computer vision systems, optical character recognition (OCR), and large language models—to operate together while remaining independent of one another.

The normal output of extraction is Evidence. Components may additionally emit proposed Claims, but no extraction stage may bypass validation or determine the final product identity.

### 6.3.1 Pipeline Overview

The extraction process follows a simple but highly extensible workflow:

Observation
      │
      ▼
Extraction Orchestrator
      │
      ├─────────────┬─────────────┬─────────────┬─────────────┐
      ▼             ▼             ▼             ▼             ▼
Metadata      Text Parser      OCR        Vision Models    LLM Extractor
Extractor
      │             │             │             │             │
      └─────────────┴─────────────┴─────────────┴─────────────┘
                            │
                            ▼
                     Evidence Repository
                            │
                            ▼
                    Claim Construction

The orchestrator is responsible only for coordinating extraction processes. It does not interpret their outputs or resolve disagreements between them.

Each extractor contributes independently to a shared repository of Evidence.

### 6.3.2 Observation Reception

The pipeline begins when an Observation enters the system.

An Observation may contain numerous information sources, including:

Listing title
Description
Images
Category
Seller-provided attributes
Price
Brand fields
Marketplace metadata
Product identifiers
Structured API fields

The Observation serves as the common input to all extraction processes.

### 6.3.3 Extraction Orchestration

Rather than passing data through a fixed sequence of transformations, the engine distributes the Observation to multiple specialised extractors.

This orchestration layer is responsible for:

selecting the appropriate extractors,
scheduling execution,
managing dependencies where necessary,
collecting generated Evidence,
handling extractor failures, and
recording execution metadata.

Importantly, orchestration concerns process management rather than reasoning. Whether an extractor succeeds or fails does not alter the behaviour of other extractors.

This loose coupling allows individual components to be upgraded or replaced without affecting the remainder of the pipeline.

### 6.3.4 Independent Extraction Processes

Each extraction process focuses on a specific form of information.

Typical examples include:

Extractor	Example Evidence Produced
Metadata Extractor	Marketplace brand, category, condition
Rule-Based Parser	Model numbers, storage capacities, colours
OCR	Text appearing within product images
Logo Detector	Manufacturer branding
Object Detector	Product type, accessories, packaging
Barcode Reader	UPC, EAN, ISBN, serial numbers
Vision-Language Model	Relationships between visual and textual features
Large Language Model	Structured entities extracted from free text

Additional extractors can be introduced at any time without requiring changes elsewhere in the architecture.

### 6.3.5 Evidence Consolidation

Once extraction completes, all generated Evidence is collected into a unified Evidence Repository.

At this stage:

duplicate Evidence may coexist,
conflicting Evidence is preserved,
low-confidence Evidence is retained,
provenance information is attached,
no prioritisation or conflict resolution occurs.

The repository therefore represents the complete body of information discovered during extraction.

It intentionally reflects uncertainty rather than attempting to eliminate it prematurely.

### 6.3.6 Separation from Reasoning

The extraction pipeline concludes once all Evidence has been generated and consolidated.

No attempt is made to answer questions such as:

Which manufacturer is correct?
Which model number should be trusted?
Is this listing for a complete product or an accessory?
Which Evidence is strongest?

These questions belong to the reasoning stages that follow.

The extraction pipeline therefore acts as an information acquisition layer whose sole purpose is to maximise the quantity and quality of recoverable Evidence.

### 6.3.7 Design Characteristics

The extraction pipeline exhibits several desirable architectural properties:

Modularity – Each extractor is independently developed and maintained.
Scalability – New extractors can be added without redesigning the pipeline.
Parallelism – Multiple extractors can execute simultaneously.
Fault tolerance – Failure of one extractor does not prevent others from contributing Evidence.
Technology independence – Rule-based systems, classical machine learning, deep learning, and future AI models can coexist within the same architecture.
Extensibility – The pipeline can evolve as new data sources and extraction techniques become available.

## 6.4 Evidence Model

The Evidence Model defines how information extracted from an Observation is represented within the Product Understanding Engine. Evidence serves as the fundamental unit of extracted knowledge, providing an objective description of something detected within the source data without asserting that it is true.

Evidence occupies the boundary between extraction and reasoning. It captures what an extractor observed, how confident it was, and where the observation originated, while deliberately avoiding any interpretation of what that observation ultimately means.

This distinction allows multiple competing interpretations to coexist until the reasoning stages evaluate them collectively.

### 6.4.1 Purpose of Evidence

The purpose of Evidence is to record observations made by extraction processes in a structured, traceable, and technology-independent manner.

Evidence exists to answer questions such as:

What was detected?
Which extractor detected it?
Where was it found?
How confident was the extractor?
What supports this observation?

Evidence does not answer questions such as:

Is this observation correct?
Should it be trusted?
Which competing observation is better?
What product does this represent?

Those questions belong to the reasoning components of the engine.

### 6.4.2 Evidence as an Observation Record

Each Evidence object represents a single observation made by one extraction process.

For example, an OCR extractor may produce:

Detected Text = "RTX 4090"
Confidence = 0.97
Location = Image 2

A logo detector may independently produce:

Detected Logo = NVIDIA
Confidence = 0.88
Location = Image 1

Neither extractor concludes that the listing is an NVIDIA RTX 4090 graphics card.

Each simply records what it observed.

### 6.4.3 Evidence is Immutable

Like Observations, Evidence is immutable.

Once created, an Evidence object is never modified.

If later processing produces a refined interpretation or additional information, new Evidence is generated rather than altering existing Evidence.

This immutability provides:

reproducibility,
auditability,
deterministic processing,
historical traceability.

Every reasoning decision can therefore be reconstructed from the original Evidence exactly as it existed during processing.

### 6.4.4 Evidence is Technology Independent

The Evidence Model is intentionally independent of the extraction technology that produced it.

Whether information originates from:

OCR,
computer vision,
barcode recognition,
regex,
statistical models,
large language models,
future AI systems,

the resulting Evidence follows the same common representation.

This abstraction allows extraction technologies to evolve without requiring changes to downstream reasoning components.

### 6.4.5 Evidence Represents Possibility, Not Truth

Evidence should be interpreted as:

"An extractor observed this."

It should never be interpreted as:

"This is correct."

For example:

OCR may detect

RTX 4090

while another OCR pass detects

RTX 4080

Both pieces of Evidence remain valid observations.

The engine intentionally preserves both until later reasoning determines which interpretation is most strongly supported.

This philosophy enables the engine to model uncertainty explicitly rather than discarding potentially valuable information.

### 6.4.6 Evidence Contains Context

An isolated value is rarely sufficient for reliable reasoning.

Consequently, each Evidence object should retain sufficient contextual information to explain both its origin and its significance.

Typical contextual information includes:

originating Observation,
extractor identity,
extraction timestamp,
extraction confidence,
source location,
extraction parameters,
supporting artefacts.

This contextual metadata allows downstream components to evaluate Evidence according to its reliability, source quality, and relevance.

### 6.4.7 Evidence Supports Explainability

One of the primary goals of the Product Understanding Engine is complete explainability.

Because every Claim is constructed from Evidence, and every Evidence object references its originating Observation, the engine can provide a complete reasoning chain.

For example:

Observation
      ↓
OCR detected "RTX 4090"
      ↓
Evidence #42
      ↓
Claim:
Model = RTX 4090
      ↓
Candidate Ranking
      ↓
Canonical Product

This traceability enables developers and users to inspect exactly why the engine reached a particular conclusion.

### 6.4.8 Design Characteristics

The Evidence Model has several important architectural properties:

Immutable – Evidence never changes after creation.
Objective – Records observations rather than conclusions.
Technology agnostic – Independent of extraction method.
Traceable – Every Evidence object links back to its Observation.
Explainable – Supports complete reasoning provenance.
Composable – Multiple Evidence objects can support a single Claim.
Extensible – New evidence types can be introduced without modifying the underlying model.

These properties ensure that Evidence remains a stable interface between extraction and reasoning.

## 6.5 Evidence Types

Although all Evidence shares a common representation, not all Evidence describes the same kind of information. Different extraction processes observe different aspects of a marketplace listing, ranging from textual content and visual characteristics to structured metadata and inferred semantic relationships.

The Product Understanding Engine therefore classifies Evidence into well-defined categories. This taxonomy standardises how extracted information is represented while allowing specialised extractors to contribute diverse forms of knowledge within a common architectural framework.

The categories described in this section are intended to be extensible. New evidence types may be introduced as the engine evolves without altering the underlying Evidence Model.

### 6.5.1 Textual Evidence

Textual Evidence represents information extracted from written language.

Typical sources include:

listing titles,
product descriptions,
seller notes,
image text detected through OCR,
specification tables,
embedded documentation.

Examples include:

"RTX 4090"
"512 GB"
"Factory Sealed"
"Founders Edition"

Textual Evidence is one of the richest sources of product information but is also highly susceptible to spelling mistakes, abbreviations, marketing language, and ambiguous terminology.

### 6.5.2 Visual Evidence

Visual Evidence represents information identified directly from images.

Unlike OCR, which extracts text appearing within an image, Visual Evidence concerns the objects and characteristics depicted.

Examples include:

product shape,
packaging,
accessories,
colour,
manufacturer logos,
physical condition,
missing components,
connector layouts.

A computer vision model may detect:

GPU present
Triple-fan cooler
NVIDIA logo
Retail box visible

Visual Evidence often complements textual information and may reveal details omitted by the seller.

### 6.5.3 Structured Metadata Evidence

Many marketplaces provide structured fields alongside the listing itself.

These fields may include:

manufacturer,
category,
condition,
price,
shipping information,
seller attributes,
marketplace identifiers.

Unlike free text, structured metadata is generally easier to parse but should not automatically be considered correct.

For example:

Brand = NVIDIA
Category = Graphics Cards
Condition = Used

These values become Evidence in exactly the same way as OCR or computer vision outputs.

### 6.5.4 Identifier Evidence

Identifier Evidence represents unique or semi-unique identifiers associated with products.

Examples include:

UPC
EAN
ISBN
MPN
SKU
Serial numbers
Manufacturer product codes

Identifiers frequently provide the strongest evidence for product identification because they often map directly to canonical product records.

However, identifiers may be:

absent,
incorrectly entered,
partially visible,
damaged,
reused,
counterfeit.

They therefore remain Evidence rather than unquestioned truth.

### 6.5.5 Semantic Evidence

Semantic Evidence represents higher-level concepts extracted from one or more sources.

Rather than identifying individual words or objects, semantic extractors identify meaning.

Examples include:

product is unopened,
listing contains multiple items,
seller indicates missing accessories,
item appears refurbished,
listing is for parts only,
bundle includes original packaging.

Semantic Evidence is frequently produced by large language models or vision-language models that analyse broader context than traditional extraction algorithms.

### 6.5.6 Relational Evidence

Some observations describe relationships between detected entities rather than the entities themselves.

Examples include:

charger belongs to laptop,
box belongs to graphics card,
battery installed in camera,
multiple products shown together,
accessory attached to main device.

These relationships become important when distinguishing between:

complete products,
accessories,
replacement parts,
bundles,
unrelated objects.

Relational Evidence enables reasoning components to interpret the structure of a listing rather than merely its contents.

### 6.5.7 Derived Evidence

Certain extraction processes generate new observations by combining previously extracted information without making product-level decisions.

Examples include:

OCR detects "4090"
Logo detector identifies NVIDIA

A downstream extraction component may produce:

Possible GPU Family Mention = NVIDIA RTX 4090

This remains Evidence because it records an observation derived from other observations rather than asserting that the listing actually represents that product.

Derived Evidence provides richer inputs to the reasoning engine while preserving the separation between extraction and decision-making.

### 6.5.8 Confidence Across Evidence Types

Every Evidence object carries an associated confidence estimate representing the extractor's belief that the observation was detected correctly.

Confidence values are local to the extractor that produced them.

Consequently:

OCR confidence should not be directly compared with object detection confidence.
Computer vision confidence should not be directly compared with LLM confidence.
Different extractors may use entirely different calibration methods.

Confidence therefore measures the reliability of the extraction process rather than the truth of the observation itself.

Reasoning components are responsible for interpreting these values appropriately.

### 6.5.9 Extensibility

The taxonomy presented here is intentionally open-ended.

Future versions of the Product Understanding Engine may introduce additional categories such as:

audio evidence,
video evidence,
temporal evidence,
behavioural evidence,
marketplace history,
external knowledge-base evidence,
review outcomes and feedback-derived Observations.

Because all evidence conforms to the same underlying Evidence Model, new evidence types can be incorporated without redesigning downstream reasoning components.

## 6.6 Evidence Provenance

Evidence is only valuable if its origin can be trusted and reconstructed. Consequently, every Evidence object within the Product Understanding Engine maintains complete provenance describing how, when, and from where it was produced.

Provenance forms the foundation of explainability throughout the engine. It allows every reasoning decision to be traced back through the supporting Evidence to the original marketplace Observation. Rather than simply knowing what was detected, the engine also records how the detection occurred.

This capability is essential for debugging, auditing, model evaluation, scientific reproducibility, and future improvements to the extraction pipeline.

### 6.6.1 Purpose of Provenance

Provenance answers fundamental questions about every piece of Evidence:

Where did this Evidence originate?
Which extractor produced it?
Which Observation was analysed?
Which source field or image was examined?
When was the extraction performed?
Which model or algorithm generated the result?
Under what configuration was it produced?

Without provenance, extracted information becomes difficult to verify, reproduce, or explain.

### 6.6.2 Provenance Chain

Every Evidence object participates in a complete provenance chain.

Marketplace Listing
        │
        ▼
Observation
        │
        ▼
Extraction Process
        │
        ▼
Evidence
        │
        ▼
Claim
        │
        ▼
Candidate Product
        │
        ▼
Canonical Product

At every stage, links are preserved rather than discarded.

This enables the complete reasoning history of any product identification to be reconstructed long after the original processing has completed.

### 6.6.3 Observation Reference

Every Evidence object maintains a reference to the Observation from which it originated.

For example:

Observation ID = OBS-104587

This identifier provides access to the original marketplace data, including:

listing title,
description,
images,
seller metadata,
structured fields,
timestamps.

Maintaining this relationship ensures that every extracted observation can be independently verified against the original source.

### 6.6.4 Extractor Provenance

Evidence also records the identity of the extractor responsible for generating it.

Typical information includes:

extractor name,
extractor version,
model version,
algorithm type,
configuration identifier.

For example:

Extractor = OCR
Version = 3.2.1
Model = PaddleOCR-v5

Recording extractor versions allows historical results to be reproduced even after extraction models are updated.

### 6.6.5 Source Location

Evidence records precisely where within the Observation the information was found.

Examples include:

title,
description,
seller attributes,
image number,
image coordinates,
OCR bounding box,
metadata field.

For example:

Source = Image 3
Bounding Box = (412, 205) – (640, 248)

or

Source = Listing Title
Character Range = 18–26

This spatial or textual localisation allows developers and users to inspect the exact evidence supporting a later claim.

### 6.6.6 Extraction Metadata

Each extraction event generates operational metadata describing how the Evidence was produced.

Examples include:

extraction timestamp,
processing duration,
extraction confidence,
hardware environment,
language settings,
image resolution,
preprocessing steps.

Although much of this information is not required for routine product identification, it becomes valuable during debugging, benchmarking, and scientific evaluation.

### 6.6.7 Supporting Artefacts

Some extraction processes generate additional artefacts that strengthen explainability.

Examples include:

OCR bounding boxes,
segmentation masks,
detected object locations,
cropped image regions,
attention heatmaps,
intermediate parsing results.

Rather than discarding these artefacts after extraction, the engine may retain references to them alongside the Evidence.

These supplementary artefacts provide visual or computational justification for the extracted observation and can greatly assist in diagnosing extraction errors or evaluating model performance.

### 6.6.8 Provenance Supports Reproducibility

Because Observations and Evidence are immutable, the engine can reproduce previous reasoning exactly.

Given:

the original Observation,
identical extractor versions,
identical configurations,

the extraction process should generate the same Evidence.

This deterministic behaviour supports regression testing, scientific comparison of extraction methods, and long-term maintenance of the Product Understanding Engine.

### 6.6.9 Provenance Supports Explainable AI

Modern AI systems increasingly require transparency in their decision-making.

Within the Product Understanding Engine, provenance enables explanations such as:

The product was identified as an NVIDIA GeForce RTX 4090 because:

OCR detected "RTX 4090" in Image 2.
The logo detector recognised an NVIDIA logo.
Marketplace metadata categorised the item as a graphics card.
A vision-language model recognised a Founders Edition cooler.
These observations collectively supported the constructed Claim.

Rather than presenting a single opaque prediction, the engine exposes the evidence trail supporting its conclusions.

This significantly improves user trust and facilitates expert review.

### 6.6.10 Design Characteristics

The provenance framework possesses several important architectural properties:

Complete – Every Evidence object records its origin.
Immutable – Provenance cannot be altered after creation.
Traceable – Every reasoning step can be followed back to the original Observation.
Reproducible – Historical processing can be repeated under identical conditions.
Auditable – Decisions can be independently inspected and verified.
Explainable – The reasoning process remains transparent to both developers and users.

These characteristics make provenance a fundamental component of the Product Understanding Engine rather than an optional metadata layer.

## 6.7 Claim Model

The Claim Model defines how the Product Understanding Engine represents structured assertions about a product. Whereas Evidence records individual observations made by extraction processes, Claims express hypotheses about product attributes that are supported by one or more pieces of Evidence.

Claims form the bridge between information extraction and product reasoning. They transform collections of heterogeneous observations into a structured representation that can be evaluated, compared, and ultimately matched against canonical products.

Importantly, a Claim is not the final truth about a product. It is a reasoned assertion whose validity depends upon the Evidence supporting it.

### 6.7.1 Purpose of Claims

Evidence answers the question:

"What did the extractors observe?"

Claims answer a different question:

"What does the engine believe this observation represents?"

For example, several pieces of Evidence may independently indicate:

OCR detected "RTX 4090"
Marketplace brand = NVIDIA
Image classifier recognised a graphics card
Vision model detected a Founders Edition cooler

Together these observations support the Claim:

Model = NVIDIA GeForce RTX 4090 Founders Edition

The Claim therefore represents an interpretation rather than a direct observation.

### 6.7.2 Claims are Structured Assertions

Every Claim represents a specific assertion regarding a product attribute.

Typical claim categories include:

Manufacturer
Product family
Model
Variant
Storage capacity
Memory size
Colour
Condition
Edition
Included accessories
Packaging state
Quantity
Completeness

By expressing product information as structured assertions, the engine can reason about each attribute independently while later combining them into a complete product identity.

### 6.7.3 Claims Are Evidence-Based

A fundamental principle of the architecture is that every Claim must be supported by Evidence.

Claims are never generated arbitrarily.

Instead, they are constructed from one or more Evidence objects.

Evidence A
      │
Evidence B
      │
Evidence C
      ▼
Claim

This requirement guarantees that every assertion made by the engine can be justified through an explicit chain of supporting observations.

### 6.7.4 Multiple Evidence Objects May Support One Claim

Many product attributes cannot be inferred reliably from a single observation.

For example, the Claim:

Manufacturer = NVIDIA

may be supported simultaneously by:

marketplace metadata,
detected logo,
OCR text,
seller description,
barcode lookup.

No individual observation is necessarily sufficient.

Instead, the engine aggregates multiple independent sources of Evidence before constructing the Claim.

This redundancy improves robustness and reduces dependence on any single extractor.

### 6.7.5 One Piece of Evidence May Support Multiple Claims

The relationship between Evidence and Claims is many-to-many.

For example, the OCR observation:

RTX 4090 Founders Edition

may contribute simultaneously to:

Manufacturer = NVIDIA
Product Family = GeForce RTX
Model = RTX 4090
Edition = Founders Edition

A single observation therefore provides support for multiple independent hypotheses.

This reuse of Evidence reduces duplication while preserving a coherent reasoning process.

### 6.7.6 Claims Maintain Provenance

Claims inherit the provenance of the Evidence from which they are constructed.

Rather than storing raw observations themselves, Claims maintain references to their supporting Evidence.

Claim
    │
    ├── Evidence #17
    ├── Evidence #42
    └── Evidence #81

This relationship enables complete explainability.

Every assertion can be traced back through its supporting observations to the original marketplace listing.

### 6.7.7 Claims Represent Beliefs, Not Certainties

Although Claims are reasoned assertions, they are not treated as absolute truth.

Multiple competing Claims may exist simultaneously.

For example:

Claim A:
Model = RTX 4090

Claim B:
Model = RTX 4080

Both Claims may be retained while additional reasoning determines which is better supported.

This explicit representation of competing hypotheses allows the engine to model uncertainty without prematurely discarding potentially valuable information.

### 6.7.8 Design Characteristics

The Claim Model possesses several important properties:

Structured – Represents specific product attributes.
Evidence-based – Every Claim is supported by one or more Evidence objects.
Traceable – Claims inherit complete provenance.
Composable – Multiple Claims combine to describe an entire product.
Explainable – Every assertion can be justified.
Extensible – New claim types can be introduced without redesigning the reasoning framework.

These characteristics establish Claims as the primary representation used by downstream reasoning and candidate evaluation components.

## 6.8 Claim Construction

Claim Construction is the process by which collections of Evidence are transformed into structured Claims. Unlike extraction, which records individual observations, Claim Construction performs the first stage of semantic reasoning within the Product Understanding Engine.

Its objective is not to identify the final product but to organise supporting observations into coherent hypotheses about individual product attributes. Each Claim therefore represents an evidence-supported interpretation that can later participate in candidate retrieval and product identification.

This stage marks the transition from information acquisition to knowledge representation.

### 6.8.1 From Evidence to Claims

Evidence consists of independent observations generated by extraction processes.

Claim Construction examines these observations collectively to determine whether they support a meaningful product attribute.

For example:

Evidence
──────────────────────────────────
OCR: "RTX 4090"
Logo: NVIDIA
Metadata: Graphics Card
Description: Founders Edition

becomes:

Claims
──────────────────────────────────
Manufacturer = NVIDIA
Product Family = GeForce RTX
Model = RTX 4090
Edition = Founders Edition

Notice that no single piece of Evidence contains the complete product description.

The Claim Construction process combines multiple observations into structured assertions.

### 6.8.2 Attribute-Centred Reasoning

Claim Construction reasons independently about each product attribute.

Rather than attempting to identify the entire product in a single step, the engine first constructs Claims for attributes such as:

manufacturer,
product family,
model,
storage,
memory,
colour,
edition,
condition,
completeness,
included accessories.

This decomposition simplifies reasoning and allows uncertainty to be managed separately for each attribute.

Later stages combine these individual Claims into complete product hypotheses.

### 6.8.3 Evidence Aggregation

Many Claims require multiple supporting observations.

The Claim Construction process therefore aggregates all Evidence relevant to a particular attribute before constructing the corresponding Claim.

For example:

OCR:
RTX 4090

Description:
NVIDIA GeForce RTX 4090

Metadata:
Brand = NVIDIA

collectively support:

Manufacturer = NVIDIA
Model = RTX 4090

Aggregation enables the engine to exploit redundancy across independent extraction processes, increasing robustness and reducing sensitivity to individual extraction errors.

### 6.8.4 Conflict Preservation

Not all Evidence agrees.

Marketplace listings frequently contain contradictory information due to seller mistakes, OCR errors, ambiguous wording, or inconsistent metadata.

For example:

OCR:
RTX 4080

Description:
RTX 4090

Rather than resolving this conflict immediately, the Claim Construction process preserves competing Claims.

Claim A:
Model = RTX 4080

Claim B:
Model = RTX 4090

Both remain available for downstream evaluation.

This philosophy ensures that uncertainty is represented explicitly rather than hidden by premature decision-making.

### 6.8.5 Claim Confidence

Each constructed Claim may be associated with a confidence estimate describing the strength of its supporting Evidence.

Unlike extractor confidence, which reflects the reliability of a single observation, Claim confidence reflects the collective support for an assertion.

Factors influencing Claim confidence may include:

number of supporting Evidence objects,
diversity of extraction methods,
quality of the originating sources,
consistency between observations,
historical extractor performance.

Importantly, Claim confidence represents confidence in the assertion, not confidence in any individual extractor.

### 6.8.6 Claim Independence

Whenever possible, Claims are constructed independently.

For example:

Manufacturer
Colour
Storage Capacity
Memory Size

may all be reasoned about separately.

This modular approach improves maintainability and allows specialised reasoning algorithms to be developed for individual attribute types.

Only during later hypothesis generation are relationships between Claims considered collectively.

### 6.8.7 Explainable Construction

Because every Claim maintains references to its supporting Evidence, the Claim Construction process remains fully explainable.

For example:

Claim:
Model = RTX 4090

Supported By:
• OCR Evidence #12
• Description Evidence #27
• Metadata Evidence #31

This explicit linkage enables users and developers to inspect the reasoning behind every constructed assertion.

No Claim exists without an evidence trail.

### 6.8.8 Design Characteristics

The Claim Construction process exhibits several key architectural properties:

Evidence-driven – Claims emerge from supporting observations.
Attribute-oriented – Product characteristics are reasoned about independently.
Conflict-aware – Competing interpretations are preserved.
Explainable – Every Claim is fully traceable.
Modular – Attribute-specific reasoning can evolve independently.
Extensible – New reasoning strategies can be incorporated without changing the Evidence Model.

## 6.9 Claim Relationships and Aggregation

Individual Claims rarely exist in isolation. A product is instead described by a collection of related Claims that collectively represent different aspects of its identity. The Product Understanding Engine therefore models Claims not as independent assertions, but as interconnected components within a larger semantic structure.

Claim Relationships define how individual assertions relate to one another, while Claim Aggregation combines compatible Claims into coherent product hypotheses. Together, these mechanisms allow the engine to reason about products in a structured and explainable manner without prematurely committing to a single interpretation.

### 6.9.1 Claims Form a Semantic Network

Each Claim describes only one aspect of a product.

For example:

Manufacturer = NVIDIA
Product Family = GeForce RTX
Model = RTX 4090
Memory = 24 GB
Edition = Founders Edition
Condition = Used

Individually, these Claims provide limited information.

Collectively, however, they describe a highly specific product.

Rather than treating Claims as unrelated values, the Product Understanding Engine represents them as interconnected semantic entities.

### 6.9.2 Attribute Relationships

Certain Claims naturally depend upon others.

For example:

Manufacturer
      │
      ▼
Product Family
      │
      ▼
Model
      │
      ▼
Variant

Similarly,

Product
      │
      ├── Memory
      ├── Storage
      ├── Colour
      ├── Condition
      └── Completeness

These relationships allow reasoning components to evaluate whether combinations of Claims are logically consistent.

For example:

Manufacturer = Apple
Model = RTX 4090

is immediately recognised as internally inconsistent.

### 6.9.3 Claim Compatibility

Not every combination of Claims can simultaneously describe a real product.

The reasoning engine therefore evaluates compatibility between Claims.

Compatible example:

Manufacturer = NVIDIA
Model = RTX 4090
Memory = 24 GB
Edition = Founders Edition

Incompatible example:

Manufacturer = AMD
Model = RTX 4090

Compatibility analysis reduces impossible combinations before candidate retrieval begins.

Importantly, incompatible Claims are not deleted. They remain available because later Evidence may reveal that an earlier interpretation was incorrect.

### 6.9.4 Evidence Sharing

Multiple Claims frequently depend upon the same Evidence.

For example:

OCR:
RTX 4090 Founders Edition

supports:

Manufacturer
Product Family
Model
Edition

Rather than duplicating the underlying observation, each Claim simply references the shared Evidence.

This design reduces redundancy while maintaining complete provenance.

### 6.9.5 Claim Aggregation

Once individual Claims have been constructed, compatible Claims are grouped together to form higher-level product descriptions.

Conceptually:

Claim
Claim
Claim
Claim
        │
        ▼
Aggregated Claim Set

An aggregated Claim set does not yet represent the final identified product.

Instead, it represents a coherent hypothesis that can later be compared against canonical products stored within the engine.

### 6.9.6 Multiple Competing Aggregations

Marketplace listings often support more than one plausible interpretation.

For example:

Evidence may support both:

Hypothesis A

Manufacturer = NVIDIA
Model = RTX 4090

and

Hypothesis B

Manufacturer = NVIDIA
Model = RTX 4080

Rather than forcing an immediate decision, the engine allows multiple aggregated Claim sets to coexist.

Each aggregated hypothesis proceeds independently into candidate evaluation.

This mirrors scientific reasoning, where competing hypotheses are retained until sufficient evidence exists to discriminate between them.

### 6.9.7 Explainable Relationships

Because every aggregated Claim maintains references to its constituent Claims, and every Claim references supporting Evidence, complete explainability is preserved.

Observation
      │
Evidence
      │
Claims
      │
Aggregated Claim Set
      │
Candidate Product

This hierarchical structure enables every product hypothesis to be decomposed into the observations that originally supported it.

### 6.9.8 Design Characteristics

The Claim Relationship framework exhibits several important architectural properties:

Hierarchical – Complex product descriptions emerge from simpler assertions.
Composable – Claims combine into larger semantic structures.
Conflict-aware – Multiple competing hypotheses may coexist.
Traceable – Relationships preserve complete provenance.
Explainable – Every aggregated hypothesis can be decomposed into supporting Claims and Evidence.
Extensible – New relationship types can be introduced without redesigning existing components.
Summary

Claim Relationships and Aggregation provide the mechanism by which individual product assertions are organised into coherent product hypotheses. By modelling compatibility, preserving competing interpretations, and maintaining explicit relationships between Claims, the Product Understanding Engine establishes a flexible and explainable semantic representation that bridges attribute-level reasoning and candidate product identification.

## 6.10 Evidence and Claim Design Patterns

The preceding sections have defined the concepts of Observations, Evidence, Claims, and their relationships. This section summarises the architectural patterns that guide their implementation throughout the Product Understanding Engine. These patterns are not individual algorithms but recurring design principles that ensure consistency, extensibility, and explainability across the system.

### 6.10.1 Immutable Data Flow

Information always flows in one direction:

Observation
      ↓
Evidence
      ↓
Claim
      ↓
Hypothesis
      ↓
Decision

Objects are never modified after creation. Instead, each stage produces a new representation built upon the previous one. This immutable pipeline improves reproducibility, simplifies debugging, and preserves a complete audit trail.

### 6.10.2 Separation of Concerns

Each architectural component has a single, clearly defined responsibility:

Component	Responsibility
Observation	Capture raw marketplace data
Extractors	Produce Evidence
Claim Construction	Transform Evidence into Claims
Aggregation	Combine compatible Claims
Candidate Retrieval	Find matching canonical products
Decision Engine	Select the most probable product

This separation reduces coupling and allows each component to evolve independently.

### 6.10.3 Many-to-Many Relationships

The engine deliberately models many-to-many relationships throughout the reasoning pipeline.

One Observation may generate many Evidence objects.
One Evidence object may support many Claims.
One Claim may depend on many Evidence objects.
One Claim may participate in multiple hypotheses.
One hypothesis may correspond to multiple candidate products.

Representing these relationships explicitly enables richer reasoning while avoiding unnecessary duplication.

### 6.10.4 Progressive Semantic Enrichment

Each processing stage increases the semantic meaning of the information it receives.

Raw Data
      ↓
Observation
      ↓
Evidence
      ↓
Claim
      ↓
Product Hypothesis
      ↓
Canonical Product

Rather than attempting to identify products immediately, the engine progressively enriches information through successive layers of abstraction.

### 6.10.5 Explainability by Design

Every architectural decision prioritises explainability.

At any point in the pipeline, the engine can answer questions such as:

Which observations supported this conclusion?
Which extractor produced this evidence?
Why was this claim constructed?
Why was one hypothesis preferred over another?

This transparency is achieved through immutable objects, explicit relationships, and complete provenance.

### 6.10.6 Technology Independence

The architecture deliberately avoids dependence on specific extraction or reasoning technologies.

Whether an observation is generated by:

OCR,
computer vision,
large language models,
classical machine learning,
rule-based systems,
or future AI techniques,

it enters the reasoning pipeline through the same Evidence representation.

This abstraction protects the architecture from technological change while allowing continuous improvement of individual components.

## 6.11 Summary

This chapter established the conceptual bridge between raw marketplace data and structured product reasoning. Beginning with immutable Observations, the chapter introduced a layered architecture that progressively transforms unstructured information into increasingly meaningful representations while preserving complete traceability throughout the process.

The chapter first defined the philosophy of information extraction, emphasising a strict separation between extraction and reasoning. Extraction processes are responsible solely for identifying observations and producing Evidence, while reasoning is deferred to downstream components. This separation of concerns enables the Product Understanding Engine to remain modular, extensible, and technology independent.

The Evidence Model was then introduced as the canonical representation of extracted information. Rather than expressing truths about a product, Evidence records objective observations together with confidence estimates, contextual information, and complete provenance. Multiple categories of Evidence—including textual, visual, metadata, identifier, semantic, relational, and derived observations—allow heterogeneous information sources to be represented within a common architectural framework.

Building upon this foundation, the chapter defined the Claim Model. Claims represent structured, evidence-supported assertions regarding individual product attributes. Unlike Evidence, which records what was observed, Claims represent reasoned interpretations that can later participate in candidate retrieval and product identification. Every Claim remains explicitly linked to its supporting Evidence, ensuring that the complete reasoning process remains transparent and reproducible.

The chapter then described Claim Construction as the first stage of semantic reasoning within the Product Understanding Engine. Evidence is aggregated into attribute-specific Claims while preserving conflicting interpretations and maintaining complete explainability. Rather than attempting to determine a final product identity immediately, the engine constructs multiple evidence-supported hypotheses that may later be evaluated against canonical product records.

Finally, the chapter introduced Claim Relationships and Aggregation, demonstrating how individual Claims combine into coherent semantic representations of products. By modelling compatibility, preserving competing hypotheses, and maintaining explicit relationships between Observations, Evidence, Claims, and aggregated hypotheses, the engine establishes a hierarchical reasoning framework capable of representing uncertainty without sacrificing explainability.

Collectively, the concepts presented throughout this chapter establish the information representation layer of the Product Understanding Engine. They define not only how information is extracted, but also how it is preserved, organised, justified, and prepared for higher-level reasoning. This layered architecture provides a robust foundation for the subsequent chapters, which will focus on transforming structured Claims into competing product hypotheses, retrieving candidate products from the canonical catalogue, evaluating those candidates using evidence-driven reasoning, and ultimately identifying the most probable representation of the marketplace listing.

# Chapter 7 — Hypothesis Generation and Candidate Retrieval

## 7.1 Introduction

The preceding chapters established how raw marketplace information is transformed into structured Observations, Evidence, and Claims. Although these representations capture increasingly rich descriptions of a marketplace listing, they do not by themselves identify the product being sold. At this stage, the engine possesses a collection of evidence-supported assertions regarding individual product attributes but has not yet determined which real-world product those assertions collectively describe.

The purpose of this chapter is to introduce the reasoning framework that transforms isolated Claims into complete product hypotheses. Rather than attempting to identify a product immediately after extraction, the Product Understanding Engine employs a hypothesis-driven approach in which multiple candidate interpretations are generated, evaluated, and progressively refined before a final decision is made.

This philosophy reflects a fundamental principle of intelligent reasoning. Real-world observations are frequently incomplete, ambiguous, or contradictory. Marketplace listings may contain typographical errors, inaccurate metadata, poor-quality images, missing specifications, or conflicting descriptions. Attempting to force an immediate product identification from such imperfect information risks premature commitment to an incorrect interpretation.

Instead, the Product Understanding Engine treats product identification as a process of hypothesis generation and evaluation. Individual Claims are combined into coherent hypotheses representing plausible descriptions of the product. Each hypothesis is then compared against a canonical product catalogue to retrieve matching candidate products. Subsequent reasoning stages evaluate these candidates using the complete body of available Evidence before selecting the most probable representation of the listing.

This approach closely resembles diagnostic reasoning employed in scientific disciplines. A physician does not diagnose a patient from a single symptom but instead considers multiple possible conditions, gathers additional evidence, evaluates competing explanations, and gradually narrows the diagnostic space. Likewise, the Product Understanding Engine maintains multiple competing product hypotheses until sufficient evidence exists to justify a final decision.

The adoption of explicit hypotheses provides several significant architectural advantages. First, uncertainty is represented directly rather than hidden within a single confidence score. Multiple plausible interpretations may coexist simultaneously, allowing downstream reasoning to evaluate them objectively. Second, explainability is substantially improved because every candidate product can be traced back through the hypothesis that generated it and the Claims and Evidence supporting that hypothesis. Finally, the hypothesis-based architecture naturally accommodates future reasoning techniques—including probabilistic inference, evidence fusion, machine learning, and knowledge graph reasoning—without requiring changes to the underlying information representation.

Figure 7.1 illustrates the transition from structured Claims to product identification.

Observation
      │
      ▼
Evidence
      │
      ▼
Claims
      │
      ▼
Hypothesis Generation
      │
      ▼
Product Hypotheses
      │
      ▼
Candidate Retrieval
      │
      ▼
Candidate Products
      │
      ▼
Candidate Evaluation
      │
      ▼
Final Product Decision

The remainder of this chapter describes how hypotheses are generated, how canonical candidate products are retrieved, and how these candidate sets provide the foundation for evidence-driven product identification. By separating hypothesis generation from final decision making, the Product Understanding Engine preserves flexibility, explainability, and robustness while ensuring that uncertainty is managed explicitly throughout the reasoning process.

## 7.2 Why Hypotheses Instead of Immediate Decisions

One of the central design principles of the Product Understanding Engine is that product identification should not be treated as a single classification problem. Instead, it is modelled as a progressive reasoning process in which multiple competing explanations are considered before selecting the most probable interpretation.

This design choice reflects both the complexity of marketplace data and the uncertainty inherent in real-world product listings. Unlike curated catalogues, marketplace listings are created by individual sellers with varying levels of expertise and attention to detail. Information may be incomplete, inconsistent, duplicated, or entirely absent. Images may be unclear, specifications omitted, and titles abbreviated or misleading. Consequently, any attempt to identify a product from a single observation or a single model prediction is likely to produce avoidable errors.

Consider the following listing title:

"4090 FE graphics card with box"

From this information alone, several interpretations remain possible:

NVIDIA GeForce RTX 4090 Founders Edition
NVIDIA GeForce RTX 4090 Founders Edition (Open Box)
NVIDIA GeForce RTX 4090 Bundle
Empty Founders Edition Box
Replacement Cooling Assembly
Retail Packaging Only

Each interpretation is initially plausible. Committing immediately to one would ignore the uncertainty present within the available observations.

Instead, the Product Understanding Engine constructs multiple hypotheses representing these alternative explanations. Additional Claims derived from product descriptions, images, metadata, and other Evidence are then used to strengthen, weaken, or eliminate competing hypotheses until only the most strongly supported candidates remain.

This approach offers several important advantages.

First, it reflects the natural process of human reasoning. Experienced domain experts rarely commit to an immediate conclusion when confronted with incomplete information. Instead, they generate several possible explanations and refine them as additional evidence becomes available.

Second, hypothesis-driven reasoning reduces the impact of extraction errors. An OCR mistake, an incorrectly classified image, or inaccurate seller metadata may temporarily support an incorrect hypothesis. However, because competing hypotheses remain active, later Evidence can compensate for earlier inaccuracies rather than allowing a single extraction error to dominate the final decision.

Third, explicit hypotheses greatly improve explainability. Rather than reporting only the selected product, the engine can explain why competing alternatives were rejected. For example:

The hypothesis "RTX 4090 Founders Edition" was preferred over "RTX 4090 Retail Box Only" because the object detector identified a complete graphics card, the marketplace category indicated a graphics card rather than accessories, and the listing description stated that the original box was included rather than being sold separately.

Such explanations are considerably more informative than a single confidence score and enable both developers and users to understand the reasoning process.

Finally, maintaining multiple hypotheses prepares the architecture for more advanced reasoning strategies introduced in later chapters. Bayesian inference, evidence fusion, probabilistic ranking, and learning-based confidence estimation all operate naturally within a hypothesis-driven framework.

For these reasons, the Product Understanding Engine deliberately postpones final product identification until competing explanations have been generated, evaluated, and compared against the complete body of available Evidence. Hypothesis generation therefore serves as the bridge between structured knowledge representation and intelligent product reasoning, establishing the foundation upon which the remainder of the reasoning engine is constructed.

## 7.3 Product Hypothesis Model

A Product Hypothesis represents a coherent, evidence-supported interpretation of the marketplace listing. Rather than identifying a product with certainty, it describes one plausible explanation that is consistent with the available Claims and Evidence at a particular point in the reasoning process.

The Product Understanding Engine may maintain multiple Product Hypotheses simultaneously. Each hypothesis competes with alternative interpretations until sufficient evidence exists to either strengthen or eliminate it. This explicit representation of competing explanations enables the engine to reason under uncertainty while maintaining complete explainability throughout the decision-making process.

Unlike individual Claims, which describe isolated product attributes, a Product Hypothesis combines multiple related Claims into a unified semantic representation capable of describing an entire product.

### 7.3.1 Purpose of a Product Hypothesis

The purpose of a Product Hypothesis is to provide an intermediate reasoning object between individual Claims and canonical product records.

Claims answer questions such as:

What manufacturer was observed?
What model number was detected?
What colour appears in the listing?

A Product Hypothesis answers a different question:

"If these Claims are collectively true, what product could this listing represent?"

Rather than committing to a final answer, the engine constructs one or more plausible explanations that can later be evaluated against known products.

### 7.3.2 Hypothesis Composition

A Product Hypothesis consists of a coherent collection of compatible Claims.

For example:

Hypothesis H1

Manufacturer = NVIDIA
Product Family = GeForce RTX
Model = RTX 4090
Edition = Founders Edition
Memory = 24 GB
Condition = Used

Each Claim contributes one aspect of the hypothesis.

Together they form a structured description that is sufficiently detailed to search for matching canonical products.

### 7.3.3 A Hypothesis is Not a Product

An important distinction exists between a Product Hypothesis and a known product record.

A hypothesis represents what the engine currently believes may be true about the listing.

A known product record is a versioned representation contained in a Knowledge Artifact. It is useful reference knowledge, not unquestionable truth. It may be incomplete, outdated, duplicated, or absent for a novel product.

For example, the hypothesis:

    Manufacturer = NVIDIA
    Model = RTX 4090
    Edition = Founders Edition

may retrieve a known product record for an NVIDIA GeForce RTX 4090 Founders Edition. That record then becomes a Candidate and must be evaluated against the Evidence.

The hypothesis acts as a retrieval and evaluation input rather than the final product identity.

### 7.3.4 Multiple Hypotheses May Coexist

Marketplace information is frequently ambiguous.

Consequently, multiple hypotheses may be generated from the same Evidence.

For example:

Hypothesis H1

Model = RTX 4090
Edition = Founders Edition
Hypothesis H2

Model = RTX 4090
Accessory = Retail Box Only
Hypothesis H3

Model = RTX 4090
Replacement Cooling Assembly

Each hypothesis is initially retained because the available Evidence does not yet conclusively distinguish between them.

This parallel reasoning strategy prevents the engine from prematurely discarding valid interpretations.

### 7.3.5 Hypotheses are Dynamic

Although Claims and Evidence remain immutable, hypotheses themselves evolve as reasoning progresses.

New Evidence may:

strengthen an existing hypothesis,
weaken a competing hypothesis,
generate entirely new hypotheses,
eliminate previously plausible interpretations.

Conceptually:

Observation
      │
Evidence
      │
Claims
      │
Hypothesis H1
Hypothesis H2
Hypothesis H3
      │
Additional Evidence
      │
Hypothesis H1 strengthened
Hypothesis H2 rejected
Hypothesis H3 weakened

Rather than modifying the underlying Evidence, the reasoning engine updates its assessment of the competing hypotheses.

### 7.3.6 Internal Consistency

Every Product Hypothesis should represent a logically consistent description of a product.

For example:

Manufacturer = NVIDIA
Model = RTX 4090
Memory = 24 GB

is internally consistent.

Whereas:

Manufacturer = Apple
Model = RTX 4090

contains mutually incompatible Claims.

Consistency checking allows impossible hypotheses to be rejected before candidate retrieval begins, reducing computational complexity and improving retrieval accuracy.

### 7.3.7 Explainable Hypotheses

Every Product Hypothesis maintains complete links to the Claims from which it was constructed.

Those Claims, in turn, maintain links to their supporting Evidence.

The reasoning hierarchy therefore becomes:

Marketplace Listing
        │
Observation
        │
Evidence
        │
Claims
        │
Product Hypothesis

This structure enables every hypothesis to be fully explained.

For example:

Hypothesis H1 was generated because:

OCR detected "RTX 4090".
Metadata identified NVIDIA.
The object detector recognised a graphics card.
The listing description referenced a Founders Edition.

Rather than producing opaque predictions, the engine exposes the complete chain of reasoning supporting each hypothesis.

### 7.3.8 Hypothesis Identity

Each Product Hypothesis should possess its own persistent identity throughout the reasoning process.

This allows subsequent components to:

attach candidate products,
record confidence estimates,
compare competing hypotheses,
monitor reasoning history,
support debugging and evaluation.

Treating hypotheses as first-class architectural objects rather than temporary data structures greatly simplifies downstream reasoning and enables future extensions such as probabilistic inference, learning-based ranking, and feedback-driven refinement.

### 7.3.9 Design Characteristics

The Product Hypothesis Model exhibits several important architectural properties:

Evidence-supported – Every hypothesis is derived from explicit Claims and Evidence.
Composable – Hypotheses combine many individual product attributes into a unified description.
Competing – Multiple hypotheses may coexist until sufficient evidence discriminates between them.
Internally consistent – Claims within a hypothesis must not contradict one another.
Explainable – Every hypothesis can be decomposed into supporting Claims and Evidence.
Persistent – Hypotheses remain identifiable throughout the reasoning process.
Extensible – Future probabilistic or learning-based reasoning methods can operate directly on hypotheses.
Summary

The Product Hypothesis Model introduces the central reasoning object of the Product Understanding Engine. By combining compatible Claims into coherent, evidence-supported interpretations, hypotheses provide the mechanism through which uncertainty is explicitly represented and managed. Rather than identifying products immediately, the engine maintains multiple competing explanations that can later be compared against canonical product records and evaluated using progressively richer evidence. This hypothesis-driven architecture forms the cornerstone of the engine's reasoning capabilities and establishes the foundation for candidate retrieval, ranking, and final product identification.

## 7.4 Hypothesis Generation

Hypothesis Generation is the process by which the Product Understanding Engine transforms collections of compatible Claims into one or more plausible product interpretations. Rather than attempting to identify a product directly from individual observations, the engine systematically constructs alternative explanations that are consistent with the available evidence.

This process represents the first stage of genuine reasoning within the architecture. It moves beyond recording observations and begins exploring the space of possible product identities. Each generated hypothesis serves as a candidate explanation that will later be evaluated against canonical product definitions.

Importantly, hypothesis generation is intentionally expansive rather than restrictive. The objective is not to identify the single correct product immediately, but to generate a comprehensive set of plausible explanations that can subsequently be refined through additional reasoning.

### 7.4.1 Objectives of Hypothesis Generation

The primary objectives of hypothesis generation are to:

transform isolated Claims into coherent product descriptions,
preserve multiple plausible interpretations,
eliminate only logically impossible combinations,
maximise recall during early reasoning,
prepare structured hypotheses for candidate retrieval.

At this stage, the engine deliberately favours completeness over precision. It is preferable to retain several plausible hypotheses than to prematurely discard the correct interpretation.

### 7.4.2 Inputs to the Generator

Hypothesis generation operates exclusively on the Claim layer.

Its inputs include:

structured Claims,
Claim relationships,
compatibility constraints,
provenance information,
confidence estimates,
domain knowledge.

The generator does not access raw marketplace observations directly.

This separation preserves the layered architecture established in earlier chapters.

Conceptually:

Observations
      │
Evidence
      │
Claims
      │
Hypothesis Generator
      │
Product Hypotheses

### 7.4.3 Compatibility Analysis

The first stage of hypothesis generation evaluates compatibility between Claims.

Compatible Claims may coexist within the same hypothesis.

For example:

Manufacturer = NVIDIA

Model = RTX 4090

Memory = 24 GB

can naturally be combined.

In contrast,

Manufacturer = NVIDIA

Manufacturer = AMD

cannot simultaneously describe the same product.

Similarly,

Storage = 512 GB

Storage = 1 TB

may indicate competing hypotheses rather than a single product.

Compatibility analysis therefore determines which Claims can participate in the same explanation.

### 7.4.4 Hypothesis Construction

Once compatibility has been established, the engine begins constructing hypotheses.

Conceptually, this resembles assembling a jigsaw puzzle.

Each compatible Claim contributes another piece of the overall product description.

For example:

Claim:
Manufacturer = Apple

Claim:
Product Family = iPhone

Claim:
Model = iPhone 15 Pro

Claim:
Storage = 512 GB

Claim:
Colour = Natural Titanium

collectively produce:

Hypothesis H1

Apple
iPhone 15 Pro
512 GB
Natural Titanium

Each hypothesis therefore represents a coherent semantic interpretation assembled from multiple independent assertions.

### 7.4.5 Branching

Uncertainty naturally creates branching within the reasoning process.

Suppose the engine possesses the following Claims:

Manufacturer = NVIDIA

Model = RTX 4090

and

Edition = Founders Edition

or

Edition = ASUS TUF Gaming

Rather than selecting one edition immediately, the generator creates two hypotheses:

H1
RTX 4090 Founders Edition
H2
RTX 4090 ASUS TUF Gaming

Both remain active until subsequent evidence favours one over the other.

Branching enables uncertainty to be represented explicitly throughout the reasoning process.

### 7.4.6 Merging

Conversely, independent Claims frequently converge upon the same explanation.

Suppose multiple extractors independently identify:

NVIDIA
RTX 4090
Graphics Card
Founders Edition

Rather than creating duplicate hypotheses, the engine merges compatible evidence into a single richer hypothesis.

Conceptually:

Claim Set A
      │
Claim Set B
      │
Claim Set C
      ▼
Single Hypothesis

Merging reduces redundancy while strengthening support for the resulting interpretation.

### 7.4.7 Pruning

Hypothesis generation deliberately postpones aggressive pruning.

Only hypotheses that are clearly impossible are removed.

Examples include:

incompatible manufacturers,
impossible product hierarchies,
mutually exclusive attributes,
invalid identifier combinations.

Hypotheses that are merely uncertain remain active.

This conservative pruning strategy minimises the risk of eliminating the correct interpretation too early.

### 7.4.8 Hypothesis Expansion

As additional Claims become available, existing hypotheses may expand.

For example:

Initial hypothesis:

NVIDIA
RTX 4090

Later Claims:

24 GB

Founders Edition

Retail Box Included

produce the expanded hypothesis:

NVIDIA
RTX 4090
24 GB
Founders Edition
Retail Box Included

Expansion progressively increases semantic richness without altering the underlying Evidence.

### 7.4.9 Explainable Generation

Every hypothesis records exactly which Claims contributed to its construction.

Conceptually:

Claim A
Claim B
Claim C
      │
      ▼
Hypothesis H1

Because each Claim already references supporting Evidence, and each Evidence references the originating Observation, every generated hypothesis remains completely explainable.

The engine can therefore answer questions such as:

Why was this hypothesis created?

or

Which observations supported this interpretation?

without requiring any additional reasoning.

### 7.4.10 Design Characteristics

The hypothesis generation process exhibits several important architectural properties:

Generative – Constructs multiple plausible explanations.
Conservative – Eliminates only impossible interpretations.
Composable – Builds complex hypotheses from simple Claims.
Branching – Explicitly represents uncertainty.
Merge-aware – Combines equivalent interpretations.
Explainable – Every hypothesis maintains complete provenance.
Extensible – New generation strategies can be incorporated without redesigning the architecture.
Summary

Hypothesis Generation transforms structured Claims into coherent, evidence-supported explanations of the marketplace listing. By analysing compatibility, constructing candidate interpretations, supporting branching and merging, and pruning only logically impossible combinations, the Product Understanding Engine creates a diverse set of product hypotheses that explicitly represent uncertainty. These hypotheses form the foundation for the next stage of reasoning, in which they are matched against canonical product definitions through candidate retrieval.

## 7.5 Candidate Retrieval

Candidate Retrieval is the process by which Product Hypotheses are matched against the canonical product knowledge base to identify the set of products that most plausibly correspond to the marketplace listing. Rather than attempting to identify a single product immediately, the objective of candidate retrieval is to efficiently construct a high-quality candidate set that contains the correct product whenever sufficient supporting evidence exists.

This distinction is fundamental. Candidate Retrieval is not a decision-making process; it is a search process. Its purpose is to maximise the probability that the correct canonical product is included within the retrieved candidate set while maintaining computational efficiency over potentially millions of known products.

Within the Product Understanding Engine, Candidate Retrieval is therefore treated as an Information Retrieval (IR) problem rather than a classification problem. Product Hypotheses act as structured queries, while the canonical product catalogue functions as a searchable knowledge base. The output of retrieval is an ordered set of candidate products that will later undergo detailed evidence-driven evaluation.

### 7.5.1 Retrieval Philosophy

The primary objective of Candidate Retrieval is high recall rather than immediate precision.

The retrieval engine should answer the question:

"Which products could plausibly match this hypothesis?"

rather than:

"Which product is correct?"

This distinction allows later reasoning stages to evaluate competing candidates using richer contextual information.

Consequently, retrieval intentionally favours returning a small number of plausible candidates over prematurely eliminating the correct product.

### 7.5.2 Retrieval Inputs

Candidate Retrieval operates on structured Product Hypotheses rather than raw marketplace data.

Typical hypothesis attributes include:

manufacturer,
product family,
model,
edition,
storage capacity,
memory size,
colour,
condition,
identifiers,
accessory status,
completeness.

These attributes collectively define the retrieval query.

Unlike conventional keyword search, retrieval therefore exploits structured semantic information rather than relying solely upon textual similarity.

### 7.5.3 The Canonical Product Knowledge Base

Candidate Retrieval searches one or more versioned product Knowledge Artifacts. Collectively, these may be presented operationally as the Canonical Product Knowledge Base (CPKB).

The CPKB may contain:

- normalised known product records;
- manufacturer and marketplace identifiers;
- aliases and abbreviations;
- structured attributes;
- product-form and compatibility relationships;
- product-family and variant relationships;
- provenance, coverage, and version information.

The CPKB is the best available product knowledge for a particular release, but it is not an unquestionable source of truth. Records may be incomplete, wrong, outdated, or missing. The correct product may therefore be absent from every retrieved Candidate Set.

Each retrieval and Decision must identify the Knowledge Artifact versions used. Catalogue absence must be represented as a coverage limitation rather than forcing selection of the nearest known product.

### 7.5.4 Retrieval as Structured Search

Traditional search engines compare text.

The Product Understanding Engine compares structured product descriptions.

Conceptually:

Product Hypothesis
        │
Structured Query
        │
Candidate Retrieval
        │
Canonical Product Knowledge Base
        │
Top-k Candidate Products

Rather than searching for exact phrases, the retrieval engine compares structured product attributes across multiple dimensions simultaneously.

This significantly improves robustness when listings contain spelling mistakes, abbreviations, or incomplete descriptions.

### 7.5.5 Coarse-to-Fine Retrieval

To achieve both scalability and accuracy, Candidate Retrieval employs a coarse-to-fine retrieval strategy.

Stage 1 — Broad Candidate Generation

The first stage rapidly identifies a relatively large pool of plausible products.

This stage prioritises recall and may use lightweight matching techniques such as:

manufacturer filtering,
product family filtering,
category constraints,
identifier lookups,
lexical similarity,
approximate nearest-neighbour search.

The objective is simply to eliminate obviously unrelated products while ensuring that the correct product remains within the candidate pool.

Stage 2 — Candidate Refinement

The second stage performs more detailed comparisons using richer product information.

Examples include:

attribute matching,
specification comparison,
semantic similarity,
compatibility constraints,
contextual relationships.

This progressively reduces the candidate set while preserving the most plausible interpretations.

Stage 3 — Evidence-Based Evaluation

The final stage (described later in this chapter) performs detailed reasoning using the complete Evidence graph.

At this point the candidate set is sufficiently small that computationally expensive reasoning becomes practical.

### 7.5.6 Hybrid Retrieval

No single retrieval strategy performs well across every marketplace listing.

The Product Understanding Engine therefore adopts a hybrid retrieval architecture combining multiple complementary retrieval methods.

Potential retrieval signals include:

Lexical Retrieval

Traditional token matching.

Useful for:

model numbers,
identifiers,
exact product names.
Structured Attribute Matching

Comparison of explicit product attributes such as:

manufacturer,
storage,
memory,
colour,
edition.
Semantic Retrieval

Vector representations allow retrieval based upon semantic similarity rather than exact wording.

Examples include:

"FE"

≈

"Founders Edition"

or

"GPU"

≈

"Graphics Card"

Identifier Retrieval

Where reliable identifiers exist (UPC, EAN, MPN), retrieval may directly access corresponding canonical products.

Identifiers frequently provide the strongest retrieval signal but are not always available.

Constraint-Based Filtering

Certain Claims impose hard constraints.

Examples:

Apple products cannot match NVIDIA products.
Laptop accessories cannot match desktop processors.
DSLR lenses cannot match smartphones.

Constraint filtering dramatically reduces the search space before more expensive similarity calculations occur.

### 7.5.7 Top-k Candidate Generation

Rather than retrieving a single product, the engine returns the highest-ranked k candidate products.

Conceptually:

Hypothesis
      │
Retrieval
      │
Candidate 1
Candidate 2
Candidate 3
Candidate 4
Candidate 5

The value of k may vary depending upon:

hypothesis confidence,
ambiguity,
product category,
computational budget.

Maintaining multiple candidates allows downstream reasoning to evaluate competing possibilities without prematurely committing to a single product.

### 7.5.8 Retrieval Explainability

Candidate Retrieval remains fully explainable.

Each retrieved product records:

which hypothesis generated it,
which retrieval methods matched,
which attributes contributed,
which constraints were satisfied,
which similarity measures were used.

For example:

Candidate retrieved because:

Manufacturer matched exactly.
Model number matched lexically.
Memory specification matched.
Semantic similarity between product titles exceeded the retrieval threshold.

This information becomes part of the overall reasoning trail and allows retrieval decisions to be independently inspected.

### 7.5.9 Scalability

The Canonical Product Knowledge Base may eventually contain millions of products spanning hundreds of marketplaces and product categories.

Consequently, Candidate Retrieval must be designed to scale efficiently.

The architecture therefore encourages:

indexed search structures,
incremental indexing,
parallel retrieval,
approximate nearest-neighbour methods where appropriate,
distributed search infrastructure,
caching of frequently accessed canonical products.

These implementation details remain independent of the conceptual retrieval model defined by this architecture.

### 7.5.10 Design Characteristics

The Candidate Retrieval architecture exhibits several defining properties:

Recall-oriented – Prioritises retaining the correct product within the candidate set.
Structured – Operates on Product Hypotheses rather than raw text.
Hybrid – Combines lexical, semantic, structured, and identifier-based retrieval.
Scalable – Supports very large canonical product catalogues.
Explainable – Every retrieved candidate includes a complete retrieval rationale.
Technology-independent – Retrieval algorithms may evolve without altering the architectural interfaces.
Progressive – Retrieval narrows the search space through successive stages of refinement.

## 7.6 Evidence-Based Candidate Evaluation

Candidate Retrieval identifies the products that could plausibly correspond to a Product Hypothesis. Candidate Evaluation determines which of those products is best supported by the available evidence.

These are fundamentally different problems.

Retrieval asks:

"Which products should we consider?"

Evaluation asks:

"Which candidate most completely explains the observed evidence?"

The Product Understanding Engine therefore separates retrieval from evaluation. This separation allows retrieval to prioritise efficiency and recall, while candidate evaluation performs deeper, evidence-driven reasoning over a much smaller search space.

Rather than treating product identification as a simple similarity comparison, the engine evaluates each candidate as a competing explanation for the observed marketplace listing.

### 7.6.1 Candidate Evaluation as Explanatory Reasoning

The Product Understanding Engine adopts an explanatory view of reasoning.

Each retrieved candidate represents a possible explanation for the marketplace listing.

The objective is therefore not simply to measure similarity, but to determine:

Which candidate explains the observed Evidence most completely, most consistently, and with the fewest contradictions?

This distinction is important.

Two candidates may appear superficially similar, yet one may explain substantially more of the available observations.

The engine therefore evaluates explanatory power rather than isolated feature similarity.

### 7.6.2 Inputs to Candidate Evaluation

Each evaluation considers three primary information sources:

Product Hypothesis
        │
        ├───────────────┐
        ▼               ▼
Supporting Claims   Supporting Evidence
        │               │
        └──────┬────────┘
               ▼
      Candidate Product

Evaluation therefore considers not only the candidate itself but also the reasoning chain that produced it.

### 7.6.3 Attribute-Level Comparison

Evaluation begins by comparing individual product attributes.

Examples include:

manufacturer,
product family,
model,
variant,
memory,
storage,
colour,
edition,
completeness,
included accessories.

Each attribute comparison contributes evidence either supporting or weakening the candidate.

For example:

Attribute	Candidate	Evidence	Result
Manufacturer	NVIDIA	NVIDIA	Match
Model	RTX 4090	RTX 4090	Match
Memory	24 GB	24 GB	Match
Edition	Founders Edition	Unknown	Neutral

Not every attribute must match perfectly.

Missing information is treated differently from contradictory information.

### 7.6.4 Positive and Negative Evidence

One of the most important design principles of the evaluation engine is that supporting and contradicting observations are considered separately.

Positive evidence strengthens a candidate.

Examples include:

exact model match,
matching identifier,
recognised manufacturer logo,
matching specifications.

Negative evidence weakens a candidate.

Examples include:

incompatible manufacturer,
impossible memory size,
conflicting product family,
contradictory identifiers.

This distinction allows the engine to explain not only why a candidate succeeded, but also why another candidate failed.

### 7.6.5 Missing Evidence

Marketplace listings are frequently incomplete.

The absence of information should not automatically count against a candidate.

For example, if a listing never mentions memory capacity, the engine should avoid assuming the candidate is incorrect.

Accordingly, Candidate Evaluation distinguishes between:

supporting evidence, which strengthens a candidate,
contradictory evidence, which weakens a candidate,
missing evidence, which remains neutral.

This principle prevents incomplete listings from being unfairly penalised.

### 7.6.6 Evidence Coverage

An important evaluation criterion is Evidence Coverage.

Evidence Coverage measures the extent to which a candidate explains the available observations.

Consider two candidates:

Candidate A explains:

manufacturer,
model,
memory,
colour,
packaging.

Candidate B explains only:

manufacturer,
model.

Although both remain plausible, Candidate A provides a more complete explanation of the marketplace listing.

The engine therefore favours candidates that maximise evidence coverage while remaining internally consistent.

### 7.6.7 Consistency

A strong candidate should not merely explain observations—it should explain them without contradiction.

For example:

Evidence:

NVIDIA
RTX 4090
24 GB

Candidate:

AMD Radeon RX 7900 XTX

Although both products are graphics cards, the candidate directly contradicts multiple observations.

Consistency therefore represents an essential component of candidate quality.

### 7.6.8 Explainable Evaluation

Every evaluation produces an explicit reasoning record.

For example:

Candidate:
NVIDIA GeForce RTX 4090 Founders Edition

Supporting Evidence
✓ OCR detected RTX 4090
✓ Metadata manufacturer = NVIDIA
✓ Vision recognised Founders Edition cooler
✓ Graphics card detected

Contradictory Evidence
None

Missing Evidence
Memory not observed
Serial number unavailable

This reasoning record enables every evaluation to be independently inspected and verified.

Rather than reporting a single score, the engine exposes the evidence supporting its conclusions.

### 7.6.9 Evaluation is Technology Independent

The architectural framework deliberately separates evaluation logic from the algorithms used to implement it.

An implementation may employ:

deterministic rule systems,
weighted scoring,
probabilistic inference,
Bayesian reasoning,
graph reasoning,
machine learning,
large language models,
hybrid approaches.

Regardless of implementation, every evaluation must produce the same conceptual outputs:

supporting evidence,
contradictory evidence,
missing evidence,
overall explanatory assessment.

This abstraction allows the evaluation engine to evolve without altering the surrounding architecture.

### 7.6.10 Design Characteristics

The Evidence-Based Candidate Evaluation Engine possesses several defining properties:

Explanatory – Evaluates how well candidates explain observed evidence.
Evidence-driven – Operates on explicit supporting and contradictory observations.
Transparent – Produces complete reasoning records.
Robust – Distinguishes contradiction from missing information.
Technology-independent – Supports multiple reasoning algorithms.
Extensible – Allows future advances in AI and probabilistic reasoning to be incorporated without redesigning the architecture.

## 7.7 Inference to the Best Explanation

The ultimate objective of the Product Understanding Engine is not simply to retrieve products that resemble the marketplace listing, but to determine which candidate provides the most complete and coherent explanation of the available observations. This reasoning strategy is known within philosophy, scientific reasoning, and artificial intelligence as Inference to the Best Explanation (IBE) or abductive reasoning.

Unlike deductive reasoning, which derives conclusions that must be true if the premises are true, or inductive reasoning, which generalises from repeated observations, abductive reasoning seeks the explanation that best accounts for the available evidence. It therefore provides an appropriate theoretical foundation for product identification, where observations are often incomplete, uncertain, or contradictory.

Within the Product Understanding Engine, every candidate product is treated as a competing explanatory hypothesis. The reasoning engine evaluates these hypotheses according to how well they account for the complete body of Evidence rather than relying solely on feature similarity or statistical classification.

### 7.7.1 Forms of Reasoning

Reasoning systems are commonly categorised into three broad forms:

Reasoning Type	Purpose	Example
Deduction	Derive conclusions that necessarily follow from known facts	"All RTX 4090 Founders Editions have 24 GB memory."
Induction	Infer general rules from repeated observations	"Most listings containing this identifier are RTX 4090 cards."
Abduction	Identify the explanation that best accounts for observed evidence	"Given all observed evidence, this listing is most plausibly an RTX 4090 Founders Edition."

The Product Understanding Engine primarily employs abductive reasoning because marketplace listings rarely provide complete certainty.

### 7.7.2 Product Identification as an Explanatory Problem

Marketplace listings are characterised by uncertainty.

Examples include:

incomplete specifications,
missing images,
OCR errors,
inaccurate metadata,
seller mistakes,
ambiguous terminology,
missing accessories,
damaged products.

Under these conditions, the objective is not to prove that a candidate is correct with absolute certainty.

Instead, the engine seeks the candidate that provides the most satisfactory explanation of the available observations.

This distinction fundamentally changes the nature of product identification.

The question becomes:

"Which candidate best explains everything we have observed?"

rather than:

"Which candidate appears most similar?"

### 7.7.3 Competing Explanations

Each retrieved candidate represents a competing explanation for the marketplace listing.

For example:

Evidence:

NVIDIA
RTX 4090
Triple-fan cooler
Original retail box
24 GB

Candidate A:

NVIDIA RTX 4090 Founders Edition

Candidate B:

ASUS RTX 4090 TUF Gaming

Candidate C:

RTX 4090 Retail Box Only

Each candidate explains part of the evidence.

However, Candidate A may explain a greater proportion of the observations while introducing fewer contradictions.

The reasoning engine therefore evaluates explanatory quality rather than simple similarity.

### 7.7.4 Characteristics of a Good Explanation

Within the Product Understanding Engine, a strong explanatory hypothesis exhibits several desirable characteristics.

Completeness

The candidate explains as much of the available Evidence as possible.

Consistency

The candidate does not contradict supported Claims or established domain knowledge.

Coherence

Individual attributes combine into a logically meaningful product.

Specificity

The candidate provides a precise explanation rather than an unnecessarily broad one.

For example:

Graphics Card

is less informative than:

NVIDIA GeForce RTX 4090 Founders Edition

Simplicity

When multiple explanations account equally well for the observations, the engine prefers the explanation requiring the fewest unsupported assumptions.

This reflects the scientific principle commonly known as Occam's Razor.

### 7.7.5 Evidence Integration

Abductive reasoning naturally integrates heterogeneous Evidence.

For example:

OCR
↓

Computer Vision
↓

Metadata
↓

Seller Description
↓

Identifiers
↓

Marketplace Category

Each observation contributes independently to the overall explanatory assessment.

The engine does not require every extractor to agree perfectly.

Instead, it evaluates how well each candidate accounts for the collective evidence.

### 7.7.6 Uncertainty Remains Explicit

An important property of abductive reasoning is that uncertainty is never hidden.

If two candidates explain the observations equally well, both remain plausible.

For example:

Candidate A
Explanation Quality = High

Candidate B
Explanation Quality = High

The engine may therefore:

retain both candidates,
request additional information,
defer final identification,
express uncertainty explicitly.

This behaviour is preferable to forcing an unjustified decision.

### 7.7.7 Explainable Decisions

Because the reasoning process is explanatory rather than purely statistical, every decision can be justified.

For example:

Selected Candidate

NVIDIA GeForce RTX 4090 Founders Edition

Reasoning

✓ Explains all recognised product identifiers.

✓ Matches detected manufacturer.

✓ Matches OCR text.

✓ Matches detected cooler design.

✓ Introduces no contradictory specifications.

Rejected alternatives can be explained using the same reasoning framework.

This capability significantly improves transparency and user trust.

### 7.7.8 Relationship to Machine Learning

The abductive reasoning framework does not replace machine learning.

Instead, machine learning becomes one source of Evidence within a broader reasoning architecture.

Computer vision, language models, embedding models, and probabilistic classifiers all contribute observations that support or weaken competing explanations.

The final decision emerges from evaluating the explanatory strength of each candidate rather than accepting the output of any individual model as authoritative.

This separation enables the architecture to incorporate future AI advances without fundamentally changing its reasoning principles.

### 7.7.9 Design Characteristics

Inference to the Best Explanation provides the Product Understanding Engine with several important properties:

Evidence-centred – Decisions emerge from the complete body of Evidence.
Hypothesis-driven – Multiple competing explanations are evaluated.
Explainable – Every decision can be justified through explicit reasoning.
Uncertainty-aware – Ambiguity is represented rather than concealed.
Technology-independent – Compatible with deterministic, probabilistic, and learning-based methods.
Scientifically grounded – Aligns the architecture with established principles of reasoning used across artificial intelligence, medicine, and the natural sciences.

## 7.8 Managing Ambiguity and Uncertainty

Real-world marketplace data is inherently uncertain. Listings may contain incomplete descriptions, conflicting specifications, poor-quality images, inaccurate metadata, or omitted information. Consequently, ambiguity is not an exceptional circumstance within the Product Understanding Engine—it is an expected characteristic of the operating environment.

Rather than attempting to eliminate uncertainty prematurely, the Product Understanding Engine explicitly represents and manages ambiguity throughout the reasoning process. Competing hypotheses, incomplete observations, and conflicting evidence are preserved until sufficient information exists to justify a more confident interpretation.

This philosophy reflects the broader architectural principle established throughout the preceding chapters: uncertainty should be represented rather than concealed.

### 7.8.1 Sources of Uncertainty

Ambiguity may arise from numerous sources, including:

incomplete marketplace listings,
seller errors,
abbreviated product names,
OCR inaccuracies,
conflicting metadata,
poor image quality,
missing specifications,
multiple products appearing within a single listing,
reused product photographs,
damaged or modified products.

Each source contributes uncertainty in different ways, requiring the reasoning engine to remain flexible rather than relying upon rigid assumptions.

### 7.8.2 Explicit Representation of Ambiguity

The Product Understanding Engine does not attempt to force every observation into a single interpretation.

Instead, ambiguity is represented explicitly through competing Product Hypotheses.

For example:

Hypothesis H1
RTX 4090 Founders Edition

Hypothesis H2
RTX 4090 Retail Box Only

Hypothesis H3
RTX 4090 Cooling Assembly

Each remains active until additional Evidence provides sufficient discriminatory power.

This explicit representation prevents potentially correct explanations from being discarded too early.

### 7.8.3 Missing Information

The absence of evidence should not automatically be interpreted as evidence against a hypothesis.

For example, a marketplace listing that omits storage capacity does not imply that the candidate possesses an incorrect storage capacity.

Accordingly, the reasoning engine distinguishes between:

Observed information
Missing information
Contradictory information

Only contradictory information actively weakens a hypothesis.

Missing information remains neutral until additional observations become available.

### 7.8.4 Conflicting Evidence

Different extraction processes may produce contradictory observations.

For example:

OCR identifies "RTX 4080"
Listing description states "RTX 4090"
Metadata specifies "Graphics Card"

Rather than selecting one observation immediately, the engine preserves all supporting Evidence and evaluates how each influences competing hypotheses.

Conflicting observations therefore become part of the reasoning process rather than errors to be discarded.

### 7.8.5 Degrees of Confidence

Not all uncertainty is binary.

Some hypotheses may be strongly supported, while others remain only weakly plausible.

Consequently, the engine represents reasoning as a spectrum of confidence rather than a simple true/false decision.

Importantly, confidence reflects the current state of available evidence and may change as additional information is acquired or new extraction techniques become available.

### 7.8.6 Deferred Decisions

There are situations in which the available Evidence does not justify a definitive product identification.

In such cases, the engine may intentionally defer its decision.

Possible outcomes include:

retaining multiple candidates,
requesting additional information,
indicating low confidence,
escalating for human review,
awaiting future evidence.

Deferring an uncertain decision is preferable to making a confident but incorrect identification.

### 7.8.7 Explainable Uncertainty

One of the strengths of the architecture is that uncertainty itself can be explained.

For example:

Product identification remains ambiguous because:

OCR and listing description disagree on the model number.
Images are insufficient to distinguish between two editions.
No product identifier is present.
Both remaining candidates explain the available evidence equally well.

Rather than simply reporting "Low Confidence," the engine identifies the specific sources of uncertainty.

### 7.8.8 Design Characteristics

The uncertainty management framework exhibits several important properties:

Explicit – Ambiguity is represented rather than hidden.
Evidence-driven – Decisions evolve as evidence accumulates.
Conservative – Uncertain hypotheses are preserved until justified.
Transparent – Sources of uncertainty remain explainable.
Adaptable – New evidence may strengthen or weaken existing hypotheses without requiring architectural changes.

## 7.9 Decision Readiness

The objective of the Product Understanding Engine is not simply to identify products, but to identify them with an appropriate degree of confidence. Consequently, before any final product decision is made, the reasoning engine evaluates whether sufficient evidence has been accumulated to justify committing to a particular candidate.

Decision Readiness represents the final assessment performed before product identification. Rather than selecting the highest-ranked candidate unconditionally, the engine determines whether the available evidence adequately supports a definitive conclusion or whether uncertainty remains sufficiently high that additional reasoning, information, or human intervention is warranted.

This distinction reinforces a central principle of the Product Understanding Engine: knowing when not to decide is as important as knowing when to decide.

### 7.9.1 Purpose of Decision Readiness

The purpose of Decision Readiness is to answer a single question:

"Do we possess sufficient evidence to justify selecting this candidate?"

Importantly, this question is different from:

"Which candidate scored highest?"

A candidate may rank first among all retrieved products while still lacking sufficient supporting evidence for a reliable identification.

Decision Readiness therefore evaluates the quality of the reasoning process rather than the numerical ranking alone.

### 7.9.2 Inputs to the Assessment

Decision Readiness considers the complete reasoning state produced by the preceding stages.

Inputs include:

retrieved candidate products,
supporting Claims,
supporting Evidence,
contradictory Evidence,
Evidence coverage,
internal consistency,
remaining ambiguity,
explanatory quality.

Rather than relying upon a single metric, the assessment considers the reasoning process as a whole.

### 7.9.3 Characteristics of a Decision-Ready Candidate

A candidate is considered ready for selection when it demonstrates the following characteristics:

Strong Evidence Support

The candidate is supported by multiple independent observations originating from different extraction processes.

High Evidence Coverage

The candidate explains a substantial proportion of the available Evidence.

Internal Consistency

The candidate introduces few or no contradictions with supported Claims.

Limited Ambiguity

Competing hypotheses are significantly less well supported.

Sufficient Specificity

The candidate identifies a concrete canonical product rather than a broad product category.

Together, these characteristics indicate that the reasoning process has converged upon a stable interpretation.

### 7.9.4 Conditions Preventing a Decision

The engine deliberately withholds a final decision when significant uncertainty remains.

Examples include:

multiple candidates with comparable explanatory quality,
contradictory identifiers,
insufficient product-specific Evidence,
incompatible high-confidence observations,
missing information critical for discrimination.

Under these circumstances, selecting a product would represent overconfidence rather than sound reasoning.

### 7.9.5 Decision Outcomes

Decision Readiness may produce several valid outcomes.

**Exact or specific identification**
A Candidate is supported at the stated model or variant level.

**Partial identification**
The Evidence supports a broader product family, type, or form but does not distinguish the exact variant.

**Ambiguous**
Several Candidates or hypotheses remain materially plausible.

**Abstained or deferred**
The available Evidence does not justify a reliable substantive Decision at the required level.

**Escalated**
Additional automated processing or human review is expected to provide useful information within the case budget.

**Unsupported domain or novel product**
The available capabilities or Knowledge Artifacts do not adequately cover the listing.

**Processing failure**
A technical problem prevented intended reasoning and is recorded separately from epistemic uncertainty.

Selecting the highest-ranked Candidate is not itself a Decision outcome. The selected level must be no more specific than the Evidence justifies.

### 7.9.6 Explainable Decisions

Every decision outcome is accompanied by a complete explanation.

For example:

Decision: Accepted

Selected Candidate

NVIDIA GeForce RTX 4090 Founders Edition

Reason

Explains 96% of observed Evidence.
No contradictory identifiers.
Complete agreement across OCR, metadata, and computer vision.
Competing hypotheses explain substantially less Evidence.

Likewise, deferred or rejected outcomes include explicit explanations describing why a definitive conclusion could not be reached.

### 7.9.7 Separation from Implementation

The Decision Readiness framework deliberately avoids prescribing specific mathematical thresholds or scoring algorithms.

An implementation may use:

deterministic decision rules,
weighted scoring systems,
probabilistic confidence models,
Bayesian decision theory,
machine learning,
reinforcement learning,
hybrid reasoning strategies.

Regardless of implementation, the architectural principle remains unchanged:

A final decision is made only when the available evidence sufficiently justifies that decision.

This separation allows future improvements to decision algorithms without altering the conceptual architecture.

### 7.9.8 Design Characteristics

The Decision Readiness framework exhibits several important architectural properties:

Evidence-driven – Decisions emerge from accumulated Evidence rather than isolated scores.
Conservative – The engine avoids unjustified certainty.
Transparent – Every outcome is accompanied by an explicit rationale.
Robust – Multiple decision outcomes are supported beyond simple success or failure.
Technology-independent – Compatible with diverse reasoning and decision algorithms.
Extensible – Future decision strategies can be integrated without redesigning the architecture.
Summary

Decision Readiness represents the final reasoning assessment performed before product identification. By evaluating evidence support, explanatory quality, ambiguity, and internal consistency, the Product Understanding Engine determines whether the available information justifies a definitive decision. This explicit assessment prevents premature commitment, preserves explainability, and ensures that confidence reflects the strength of the underlying reasoning rather than the output of any individual algorithm.

# Chapter 8 — Evidence Fusion and Confidence Reasoning

## 8.1 Introduction

The preceding chapters established how marketplace Observations become Evidence, Claims, Product Hypotheses, Candidates, and Decisions. These objects are produced by heterogeneous sources with different reliability, coverage, and failure modes.

This chapter defines how the PUE reasons about that variation without collapsing every uncertainty into one universal score.

Evidence represents observed or extracted information. Confidence is always confidence in a defined proposition or process, such as extraction accuracy, Claim support, Candidate fit, or Decision correctness at a stated identification level. Probability is one possible calibrated mathematical interpretation of a confidence value; it must not be assumed automatically.

The objective is not to prescribe one fusion algorithm. Deterministic rules, weighted evidence models, Bayesian inference, belief functions, machine learning, and hybrid approaches may all be used if they preserve provenance, contradictions, score meaning, and calibration status.

## 8.2 Why Evidence Fusion is Necessary

The Product Understanding Engine acquires information from numerous heterogeneous sources, each observing different aspects of a marketplace listing. No single source can be assumed to provide a complete or entirely accurate representation of the product. Consequently, robust product identification requires the integration of multiple complementary observations rather than reliance upon any individual source.

Evidence Fusion is the process through which independent observations are combined into a coherent assessment of the product being described. Rather than treating each observation as equally authoritative, the Product Understanding Engine evaluates the collective body of available evidence, considering both agreement and disagreement while preserving the provenance and quality of every observation.

This approach reflects a fundamental architectural principle established throughout this document:

Reliable conclusions emerge from the convergence of multiple independent observations rather than from isolated pieces of evidence.

Accordingly, Evidence Fusion is not an optional enhancement but a core component of the reasoning architecture.

### 8.2.1 Multiple Sources of Evidence

Marketplace listings may provide information through a wide variety of channels.

Examples include:

marketplace metadata,
product titles,
product descriptions,
computer vision,
optical character recognition,
product identifiers,
seller attributes,
historical listings,
manufacturer catalogues,
external knowledge bases.

Each source observes the product from a different perspective and therefore contributes distinct Evidence to the reasoning process.

For example, OCR may identify a model number printed on the product, while computer vision recognises its physical appearance and metadata specifies the manufacturer. Individually, these observations may be incomplete. Together, they often provide a substantially stronger explanation.

### 8.2.2 No Single Source is Perfect

Every evidence source possesses inherent limitations.

For example:

Evidence Source	Typical Limitations
OCR	Poor image quality, partial text, reflections
Computer Vision	Occlusion, unusual viewing angles, damaged products
Metadata	Seller mistakes, incorrect categories
Product Titles	Abbreviations, marketing language, omissions
Descriptions	Typographical errors, incomplete specifications
External Databases	Missing or outdated products

Consequently, the Product Understanding Engine deliberately avoids granting absolute authority to any individual observation.

Instead, confidence emerges through the collective behaviour of multiple sources.

### 8.2.3 Complementary Evidence

Different observations frequently complement one another.

For example:

Marketplace Title
"NVIDIA RTX4090 FE"

↓

OCR
"24 GB"

↓

Computer Vision
Founders Edition cooler detected

↓

Metadata
Manufacturer = NVIDIA

No single observation completely identifies the product.

However, together they provide a coherent explanation that strongly supports a specific canonical product.

Evidence Fusion therefore exploits the complementary strengths of heterogeneous information sources.

### 8.2.4 Agreement Strengthens Confidence

When multiple independent observations support the same interpretation, confidence naturally increases.

For example:

OCR identifies RTX 4090.
Product title contains RTX 4090.
Computer vision recognises an RTX 4090 Founders Edition cooler.
Manufacturer metadata specifies NVIDIA.

Although each observation may contain some uncertainty, their collective agreement substantially strengthens the explanatory hypothesis.

Importantly, the increase in confidence arises from the agreement itself rather than from any single observation.

### 8.2.5 Disagreement Reveals Uncertainty

Evidence sources do not always agree.

For example:

OCR identifies RTX 4080.
Seller title states RTX 4090.
Metadata specifies graphics card.
Computer vision cannot distinguish the model.

Such disagreement does not necessarily indicate that one source is incorrect.

Instead, it represents uncertainty that must be explicitly preserved within the reasoning process.

The Product Understanding Engine therefore treats disagreement as informative evidence rather than as an exceptional condition.

### 8.2.6 Evidence Fusion is Explainable

Unlike many machine learning systems that expose only a final confidence score, the Product Understanding Engine maintains a complete record of how confidence was established.

For every conclusion, the engine can identify:

which observations supported the decision,
which observations contradicted it,
which observations were unavailable,
how conflicting information was resolved,
why alternative interpretations were rejected.

This explicit reasoning trail forms a central component of the architecture's commitment to explainability.

### 8.2.7 Architectural Principles

The Evidence Fusion framework is founded upon several key principles:

Multi-source – Decisions incorporate diverse observations.
Complementary – Different sources contribute different information.
Transparent – All reasoning remains traceable.
Conservative – Disagreement reduces confidence rather than being ignored.
Extensible – New evidence sources can be incorporated without redesigning the architecture.
Technology-independent – The conceptual model is independent of the algorithms used to perform evidence fusion.

These principles ensure that the reasoning process remains robust as new extraction techniques and AI models become available.

## 8.3 Evidence Quality

The preceding sections established that the Product Understanding Engine integrates Evidence originating from multiple heterogeneous sources. However, before Evidence can be meaningfully combined, the reasoning engine must first consider the quality of the individual observations from which that Evidence was derived.

Not all observations possess equal reliability. Two observations may support the same Claim while differing substantially in their trustworthiness, completeness, or susceptibility to error. Consequently, the Product Understanding Engine distinguishes between the content of an observation and the quality of that observation.

Evidence Quality represents an assessment of the reliability and usefulness of an individual piece of Evidence prior to its participation in the reasoning process. It characterises the observation itself rather than the confidence of any subsequent product identification.

This distinction forms an important architectural principle:

Evidence possesses quality before reasoning produces confidence.

### 8.3.1 Evidence Quality versus Confidence

Although closely related, Evidence Quality and Confidence describe different concepts.

Evidence Quality refers to the inherent reliability of an individual observation.

Confidence refers to the degree of support for a reasoning outcome after all available Evidence has been considered.

For example:

A perfectly legible product identifier extracted from a high-resolution image represents high-quality Evidence.

Whether that observation ultimately produces a high-confidence product identification depends upon how it interacts with all other available Evidence.

Accordingly, Evidence Quality is an input to reasoning, whereas Confidence is an output of reasoning.

### 8.3.2 Sources of Evidence Quality

Numerous factors influence the quality of an observation.

Examples include:

Observation Quality
image resolution,
lighting,
motion blur,
viewing angle,
occlusion,
completeness.
Extraction Quality
OCR confidence,
vision model confidence,
language model certainty,
parsing reliability,
identifier validation.
Source Reliability
manufacturer catalogue,
marketplace metadata,
seller description,
historical database,
human annotation.

Different information sources naturally exhibit different levels of expected reliability.

Contextual Quality

Evidence should also be interpreted within its surrounding context.

For example:

Is the observation consistent with neighbouring observations?
Does it originate from a trusted marketplace?
Has the seller demonstrated historical accuracy?
Does the observation occur repeatedly across independent sources?

Context therefore contributes to the overall assessment of Evidence Quality.

### 8.3.3 Evidence Quality is Multi-Dimensional

Evidence Quality cannot generally be reduced to a single characteristic.

Instead, it may be viewed as comprising several complementary dimensions.

Possible dimensions include:

reliability,
completeness,
clarity,
specificity,
consistency,
provenance,
recency.

For example, a manufacturer database may exhibit excellent reliability but poor recency if recently released products have not yet been added.

Similarly, an OCR observation may possess excellent clarity but limited completeness if only part of the product label is visible.

The architecture therefore treats Evidence Quality as a structured property rather than a single scalar value.

### 8.3.4 Quality is Independent of Agreement

An important architectural principle is that high-quality Evidence may still disagree with other high-quality Evidence.

For example:

OCR:
RTX 4080
Quality: High

↓

Marketplace Metadata:
RTX 4090
Quality: High

The disagreement does not imply that either observation is poor quality.

Instead, it indicates that the reasoning engine must determine which explanation best accounts for the conflict.

Separating Evidence Quality from agreement prevents the architecture from incorrectly penalising reliable observations simply because they disagree.

### 8.3.5 Quality is Preserved

Evidence Quality is assigned when Evidence is created and remains attached throughout the reasoning process.

Observation
      ↓
Evidence
+ Evidence Quality
      ↓
Claims
      ↓
Hypotheses
      ↓
Evidence Fusion
      ↓
Decision

Preserving quality information throughout the pipeline enables later reasoning stages to incorporate it without requiring the original observation to be re-evaluated.

This also strengthens explainability, as every reasoning step retains access to the quality characteristics of the Evidence upon which it depends.

### 8.3.6 Technology Independence

The Product Understanding Engine deliberately avoids prescribing how Evidence Quality should be calculated.

Implementations may estimate quality using:

deterministic heuristics,
confidence outputs from machine learning models,
statistical quality measures,
probabilistic estimators,
calibration models,
human validation,
hybrid approaches.

Regardless of implementation, the architectural role of Evidence Quality remains unchanged: it characterises the reliability of individual observations before evidence fusion and reasoning take place.

### 8.3.7 Design Characteristics

The Evidence Quality framework exhibits several defining properties:

Observation-centric – Evaluates individual Evidence rather than final decisions.
Multi-dimensional – Captures multiple aspects of reliability.
Persistent – Remains associated with Evidence throughout the reasoning process.
Explainable – Enables the engine to justify why certain observations influenced a decision more strongly than others.
Technology-independent – Supports diverse quality estimation techniques.
Extensible – Additional quality dimensions may be incorporated without altering the overall architecture.

## 8.4 Evidence Fusion Framework

The Product Understanding Engine derives product identifications by combining numerous heterogeneous observations into coherent explanatory hypotheses. This process requires more than simply accumulating supporting Evidence; it requires a principled mechanism through which individual observations may be integrated while preserving their provenance, quality, and relationships.

Evidence Fusion represents the architectural process responsible for integrating individual pieces of Evidence into a unified assessment of competing Product Hypotheses. Rather than relying upon any single observation, the reasoning engine considers the collective contribution of all available Evidence while accounting for agreement, contradiction, uncertainty, and Evidence Quality.

Importantly, Evidence Fusion is defined as a conceptual process rather than a specific algorithm. The architecture therefore separates the principles governing evidence integration from the mathematical techniques used to implement them.

### 8.4.1 Purpose of Evidence Fusion

The objective of Evidence Fusion is to transform numerous individual observations into a coherent body of reasoning capable of supporting product identification.

Specifically, the framework seeks to:

integrate heterogeneous Evidence,
preserve Evidence provenance,
account for Evidence Quality,
recognise complementary observations,
identify contradictory information,
maintain explainability,
support uncertainty throughout the reasoning process.

Evidence Fusion therefore serves as the bridge between Evidence representation and confidence assessment.

### 8.4.2 Inputs to Evidence Fusion

Evidence Fusion operates upon the complete reasoning state accumulated by previous architectural stages.

Inputs include:

Observations,
Evidence,
Evidence Quality,
Claims,
Product Hypotheses,
Candidate Products.

Each component contributes different information.

For example:

Observation
        ↓
Evidence
        ↓
Evidence Quality
        ↓
Claims
        ↓
Hypotheses
        ↓
Candidate Products
        ↓
Evidence Fusion

Rather than discarding earlier reasoning, Evidence Fusion integrates information accumulated throughout the complete pipeline.

### 8.4.3 Fusion is Evidence-Centric

A central architectural principle of the Product Understanding Engine is that Evidence—not algorithms—forms the primary object of reasoning.

Algorithms may evolve over time.

Evidence should not.

Accordingly, fusion operates directly upon structured Evidence objects and their associated metadata rather than upon opaque intermediate model outputs.

This distinction provides several important advantages:

improved explainability,
easier validation,
algorithm independence,
long-term maintainability,
reproducible reasoning.

### 8.4.4 Progressive Evidence Integration

Evidence Fusion is not viewed as a single computational step.

Instead, the Product Understanding Engine progressively accumulates Evidence as new observations become available.

For example:

Marketplace Metadata
        ↓
Initial Evidence

↓

OCR
        ↓
Additional Evidence

↓

Computer Vision
        ↓
Additional Evidence

↓

External Catalogue
        ↓
Additional Evidence

↓

Updated Reasoning

The reasoning process therefore evolves continuously as new information becomes available.

This progressive architecture allows the engine to refine conclusions without reconstructing the reasoning process from the beginning.

### 8.4.5 Independent and Dependent Evidence

Not all Evidence contributes equally.

Some observations originate from genuinely independent sources.

Others are closely related.

For example:

Independent:

OCR
Computer Vision
Marketplace Metadata

Dependent:

Seller Title
Seller Description

Both textual fields may originate from the same seller and therefore should not necessarily be treated as independent confirmation.

Recognising dependence prevents the reasoning engine from unintentionally overestimating confidence simply because similar information appears multiple times.

### 8.4.6 Supporting and Contradictory Evidence

Evidence Fusion considers both positive and negative contributions.

Supporting Evidence increases the plausibility of a Product Hypothesis.

Contradictory Evidence weakens it.

Importantly, contradictory Evidence is preserved rather than discarded.

For example:

Evidence A
RTX 4090

✓ Supports Candidate 1

✗ Contradicts Candidate 2

Maintaining contradictory observations enables the reasoning engine to explain both accepted and rejected hypotheses.

### 8.4.7 Fusion Produces Reasoning, Not Decisions

Evidence Fusion does not identify the final product.

Instead, it produces an enriched reasoning state.

This reasoning state includes:

integrated supporting Evidence,
integrated contradictory Evidence,
unresolved uncertainty,
explanatory relationships,
confidence inputs.

Final product selection remains the responsibility of the Decision Readiness stage introduced in the previous chapter.

This separation preserves a clear distinction between reasoning and decision making.

### 8.4.8 Technology Independence

The Product Understanding Engine deliberately separates the architecture of Evidence Fusion from the algorithms that perform it.

Possible implementations include:

weighted aggregation,
probabilistic reasoning,
Bayesian inference,
belief function theory,
graph-based reasoning,
machine learning,
hybrid reasoning systems.

Regardless of implementation, the conceptual responsibilities of Evidence Fusion remain unchanged.

### 8.4.9 Design Characteristics

The Evidence Fusion framework exhibits several defining properties:

Evidence-centric – Operates upon structured Evidence rather than opaque model outputs.
Progressive – Integrates new observations incrementally.
Explainable – Preserves complete reasoning provenance.
Conservative – Maintains contradictory observations explicitly.
Technology-independent – Supports multiple mathematical implementations.
Extensible – Accommodates future evidence sources and reasoning techniques.

## 8.5 Confidence and Probability

The terms confidence and probability must be used precisely.

The PUE does not possess one generic confidence value. Instead, confidence is attached to a defined target and question. Examples include:

- extraction confidence: was a value detected correctly from the source?;
- Claim support: how strongly does the Evidence support a proposition?;
- Candidate fit: how well does a Candidate agree with the hypothesis?;
- Candidate distinguishability: can the available Evidence separate leading alternatives?;
- Decision confidence: how likely is the published Decision to be correct at its stated identification level?;
- review confidence: how confident is a reviewer in a correction?;
- calibration status: does the numerical value correspond with observed correctness?.

Probability is a formal mathematical quantity. A value may be described as a probability only where the model, target event, population, and calibration evidence are defined.

A score such as lexical similarity or model softmax output may still be useful for ranking. It must retain its original meaning and must not be presented as a probability of correct product identity without validation.

Confidence evolves as the reasoning state changes. New Evidence may increase Claim support while simultaneously revealing that two variants remain indistinguishable. The final output should therefore preserve the dimensions needed to explain both what is known and what remains uncertain.

## 8.6 Evidence Independence

The Product Understanding Engine derives confidence by integrating observations originating from multiple evidence sources. However, the contribution of additional observations depends not only upon their quality but also upon their independence. Two observations that originate from the same underlying source should not necessarily provide twice the evidential support of a single observation.

Evidence Independence describes the degree to which individual observations contribute unique information to the reasoning process. Independent observations provide separate perspectives on the product and therefore strengthen explanatory support. Dependent observations, by contrast, may simply repeat the same underlying information and should be interpreted accordingly.

Recognising evidence independence prevents the reasoning engine from overestimating confidence through the repeated counting of equivalent or closely related observations.

### 8.6.1 Independent Observations

Independent observations arise from sources that measure different characteristics of the product or obtain information through different mechanisms.

Examples include:

Computer vision identifies the physical appearance of a product.
OCR extracts printed text.
Marketplace metadata specifies the manufacturer.
A barcode identifies the exact product.
A manufacturer catalogue confirms the specification.

Each source contributes distinct information.

Agreement between these independent observations provides stronger support than repeated agreement within a single information source.

### 8.6.2 Dependent Observations

Not all observations are independent.

Many marketplace attributes originate from the same seller or are automatically copied from one another.

Examples include:

Product title
Product description
Product subtitle
Product tags

These fields may all contain the same incorrect model number because they were entered by the same individual.

Similarly:

Title
↓

Description
↓

Subtitle

may represent repeated expressions of one underlying observation rather than three genuinely independent confirmations.

The Product Understanding Engine therefore distinguishes repeated information from independent evidence.

### 8.6.3 Correlated Evidence

Some observations are neither fully independent nor completely dependent.

For example:

OCR and computer vision both analyse the same image.
Multiple photographs depict the same physical product.
Two OCR engines analyse the same text region.

Although produced by different extraction processes, these observations are partially correlated because they originate from a common underlying object.

Recognising such relationships prevents confidence from increasing disproportionately through correlated observations.

### 8.6.4 Evidence Lineage

The architecture therefore maintains the lineage of every observation.

Each Evidence object records its origin, extraction process, and relationships to earlier observations.

For example:

Marketplace Image
        │
 ┌──────┴────────┐
 │               │
OCR        Computer Vision
 │               │
Evidence A   Evidence B

Although Evidence A and Evidence B are produced by different extractors, they share a common originating observation.

This lineage enables later reasoning stages to recognise potential dependencies during evidence fusion.

### 8.6.5 Independence Strengthens Explanations

Agreement among genuinely independent observations provides substantially stronger explanatory support than repeated agreement among dependent observations.

For example:

Independent agreement:

OCR detects "RTX 4090"
Barcode resolves to RTX 4090
Manufacturer metadata identifies RTX 4090

This convergence represents multiple independent observations supporting the same hypothesis.

By contrast:

Title says RTX 4090
Description says RTX 4090
Subtitle says RTX 4090

may simply represent one repeated seller assertion.

Although useful, the latter provides less independent evidential support.

### 8.6.6 Independence is Not Binary

Evidence Independence should not necessarily be viewed as a simple yes-or-no property.

Relationships may exist along a spectrum.

Examples include:

Fully independent observations.
Partially correlated observations.
Closely related observations.
Direct duplicates.

The architecture therefore treats independence as a conceptual relationship rather than a binary classification.

This allows future implementations to estimate dependency using deterministic rules, statistical models, or learned representations without altering the architecture.

### 8.6.7 Architectural Implications

Maintaining explicit independence information provides several important advantages.

It enables the reasoning engine to:

avoid double counting evidence,
recognise corroboration from genuinely independent sources,
preserve explainability,
improve confidence estimation,
support future probabilistic reasoning,
reduce systematic overconfidence.

These capabilities become increasingly important as the number of evidence sources grows.

### 8.6.8 Design Characteristics

The Evidence Independence framework exhibits several defining properties:

Lineage-aware – Tracks the origin of every observation.
Relationship-oriented – Represents dependencies between observations.
Explainable – Justifies why some observations contribute more strongly than others.
Technology-independent – Independent of any specific statistical methodology.
Extensible – Supports increasingly sophisticated dependency models over time.

## 8.7 Evidence Weighting

Within the Product Understanding Engine, not all Evidence contributes equally to the reasoning process. Although every observation may provide useful information, differences in reliability, independence, provenance, quality, and contextual relevance mean that individual observations should exert differing levels of influence when evaluating competing Product Hypotheses.

Evidence Weighting provides the architectural framework through which these differences are recognised. Rather than treating all observations as equally informative, the reasoning engine evaluates the relative contribution of each piece of Evidence while preserving transparency and explainability.

Importantly, Evidence Weighting is defined as an architectural principle rather than a specific mathematical calculation. The framework specifies what factors should influence evidential contribution without prescribing how those factors must be combined.

### 8.7.1 Why Weighting is Necessary

If all Evidence were treated equally, unreliable observations could exert the same influence as highly reliable observations.

For example:

A verified manufacturer identifier generally provides stronger evidence than a seller-written description.
A high-quality barcode scan typically provides stronger evidence than an ambiguous OCR result.
Multiple independent observations generally provide stronger support than repeated statements from the same source.

Treating all observations identically would therefore reduce both accuracy and explainability.

Evidence Weighting enables the reasoning process to reflect these differences appropriately.

### 8.7.2 Factors Influencing Evidence Weight

The contribution of Evidence may depend upon multiple characteristics.

These include:

Evidence Quality,
source reliability,
Evidence Independence,
provenance,
contextual relevance,
specificity,
completeness,
consistency with other observations,
recency where applicable.

No single characteristic necessarily determines evidential influence.

Instead, weighting reflects the combined assessment of multiple factors.

### 8.7.3 Weight is Context-Dependent

The influence of a particular observation may vary according to the reasoning context.

For example, a barcode may be decisive when identifying a retail product but unavailable for second-hand or customised items.

Similarly, computer vision may provide strong evidence for distinctive products while contributing less for visually similar variants.

Evidence Weighting therefore adapts to the information available rather than relying upon fixed universal priorities.

### 8.7.4 Weight is Not Trust

Evidence Weighting should not be interpreted as a direct measure of trustworthiness.

An observation may be highly trustworthy while contributing relatively little because it provides information already established by other independent observations.

Conversely, a moderate-quality observation may become highly influential if it introduces new information unavailable elsewhere.

Weight therefore represents contribution to the reasoning process rather than an intrinsic property of the Evidence itself.

### 8.7.5 Dynamic Weighting

The influence of Evidence may change as additional observations become available.

Initially, an OCR result may strongly influence reasoning because little other information exists.

Subsequent barcode identification or manufacturer metadata may either reinforce or supersede that contribution.

Weighting therefore evolves alongside the reasoning process rather than remaining fixed throughout execution.

### 8.7.6 Explainable Weighting

Every significant contribution to the reasoning process should remain explainable.

For example:

Candidate A received greater support because:

Manufacturer identifier matched exactly.
Barcode resolved uniquely.
OCR agreed with both observations.
Seller description provided no contradictory information.

The architecture therefore records not only the outcome of weighting but also the reasoning behind that assessment.

This enables transparent inspection, validation, and future refinement.

### 8.7.7 Architectural Independence

The Product Understanding Engine deliberately avoids prescribing a specific weighting algorithm.

Possible implementations include:

deterministic scoring,
expert-defined rules,
Bayesian likelihood weighting,
belief functions,
graph-based propagation,
learned neural weighting,
reinforcement learning,
hybrid approaches.

Regardless of implementation, the conceptual purpose of weighting remains unchanged.

### 8.7.8 Relationship to Previous Components

Evidence Weighting integrates several concepts introduced earlier in this chapter.

Conceptually:

Observation
        ↓
Evidence
        ↓
Evidence Quality
        ↓
Evidence Independence
        ↓
Evidence Weighting
        ↓
Evidence Fusion
        ↓
Confidence

Weighting therefore acts as the bridge between evaluating individual observations and combining them into coherent reasoning.

### 8.7.9 Design Characteristics

The Evidence Weighting framework possesses several defining properties:

Multi-factor – Incorporates quality, independence, provenance, and context.
Dynamic – Adapts as new observations become available.
Explainable – Every weighting decision can be justified.
Technology-independent – Supports multiple mathematical implementations.
Reasoning-centric – Measures evidential contribution rather than intrinsic truth.

## 8.8 Agreement and Conflict

The Product Understanding Engine evaluates product hypotheses by integrating evidence originating from multiple heterogeneous sources. As additional observations become available, they may either reinforce one another or introduce competing explanations. The architecture therefore distinguishes between agreement and conflict as fundamental properties of the reasoning process.

Agreement occurs when multiple observations consistently support the same explanatory hypothesis. Conflict occurs when observations support incompatible hypotheses or provide mutually inconsistent information. Both situations are considered informative. Agreement increases support for a hypothesis, whereas conflict represents uncertainty requiring further reasoning rather than immediate rejection.

Accordingly, the architecture treats agreement and conflict as complementary components of evidence evaluation rather than opposite outcomes.

### 8.8.1 Agreement Between Independent Evidence

The strongest support for a Product Hypothesis arises when multiple independent observations converge upon the same conclusion.

For example:

Computer vision identifies an RTX 4090 graphics card.
OCR extracts "RTX 4090".
A barcode resolves to the same product.
Manufacturer metadata confirms the model.

Each observation originates from a different evidential pathway. Their agreement therefore provides substantially stronger support than repeated assertions originating from a single source.

Agreement between independent observations increases the explanatory strength of the corresponding hypothesis while remaining fully traceable and explainable.

### 8.8.2 Agreement Does Not Guarantee Correctness

Although agreement generally strengthens confidence, agreement alone does not establish truth.

Multiple observations may share a common source of error.

For example:

Marketplace metadata is copied directly from the seller's title.
OCR extracts text from an incorrect product label.
Multiple online catalogues reproduce the same inaccurate information.

In such cases, apparent agreement may reflect shared misinformation rather than independent confirmation.

The architecture therefore evaluates agreement in conjunction with Evidence Independence, provenance, and Evidence Quality.

### 8.8.3 Conflict Between Evidence

Conflict occurs whenever observations favour incompatible explanations.

Examples include:

OCR identifies "RTX 4080".
Manufacturer metadata specifies "RTX 4090".

or

Computer vision classifies a laptop.
Marketplace category identifies a desktop graphics card.

Such conflicts do not necessarily indicate system failure. Instead, they represent uncertainty within the available Evidence.

Rather than discarding conflicting observations, the Product Understanding Engine preserves them explicitly so that later reasoning stages can evaluate competing explanations.

### 8.8.4 Conflict Drives Further Reasoning

Conflict should be viewed as an opportunity for additional reasoning rather than an error requiring immediate resolution.

Conflicting observations may arise because:

Evidence is incomplete.
Observations are ambiguous.
Extraction errors occurred.
Marketplace information is incorrect.
Multiple product variants exist.
The product is previously unseen.

The architecture therefore allows conflicting hypotheses to coexist until sufficient Evidence becomes available to justify a decision.

This behaviour reflects the abductive reasoning principles introduced earlier in the manuscript.

### 8.8.5 Degrees of Agreement and Conflict

Agreement and conflict are not binary concepts.

Evidence may:

strongly agree,
partially agree,
weakly support,
weakly conflict,
strongly conflict,
remain unrelated.

Recognising these varying relationships enables future implementations to model evidential interactions more realistically while preserving the conceptual architecture presented here.

### 8.8.6 Preserving Competing Explanations

One of the defining characteristics of the Product Understanding Engine is its ability to preserve multiple competing hypotheses during reasoning.

For example:

Evidence

↓

Hypothesis A
Supported by OCR

Hypothesis B
Supported by Manufacturer Metadata

↓

Further Evidence Required

Rather than prematurely selecting a single explanation, the architecture maintains competing interpretations until the accumulated body of Evidence sufficiently favours one hypothesis.

This approach reduces the likelihood of irreversible reasoning errors arising from incomplete information.

### 8.8.7 Architectural Implications

Recognising agreement and conflict provides several important architectural benefits.

It enables the reasoning engine to:

strengthen confidence through independent corroboration,
preserve contradictory Evidence,
delay premature decisions,
support explainable reasoning,
accommodate incomplete observations,
provide transparent justification for final decisions.

These capabilities become increasingly important as the diversity and complexity of Evidence sources increases.

### 8.8.8 Design Characteristics

The Agreement and Conflict framework exhibits several defining properties:

Symmetrical – Treats agreement and conflict as equally informative.
Evidence-centred – Evaluates relationships between observations rather than isolated values.
Explainable – Records why observations reinforce or contradict one another.
Uncertainty-aware – Preserves conflicting information until sufficient evidence exists.
Technology-independent – Applicable across deterministic, probabilistic, and hybrid reasoning systems.

## 8.9 Formal Models of Uncertainty

The preceding sections established the architectural principles through which observations become evidence, evidence is evaluated, and competing hypotheses are assessed. These principles describe how reasoning should be organised but intentionally avoid prescribing how uncertainty should be quantified.

To operationalise reasoning, the Product Understanding Engine requires a formal model capable of representing uncertainty and combining evidence in a mathematically consistent manner. Numerous such models exist within statistics, artificial intelligence, and information theory, each possessing distinct assumptions, strengths, and limitations.

Rather than prescribing a single mathematical framework, the Product Understanding Engine adopts an architecture-first philosophy. The architecture defines the required reasoning behaviours, while the mathematical framework provides one possible implementation of those behaviours.

Consequently, multiple uncertainty models may satisfy the architectural requirements presented throughout this chapter.

### 8.9.1 Architectural Requirements

Any uncertainty model adopted within the Product Understanding Engine should support the core architectural principles established previously.

Specifically, an appropriate framework should:

integrate heterogeneous evidence,
represent varying evidence quality,
accommodate differing levels of evidence independence,
preserve contradictory observations,
represent incomplete information,
support competing hypotheses,
produce explainable confidence assessments,
evolve as new observations become available.

These requirements arise from the architecture itself rather than from any particular mathematical formalism.

### 8.9.2 Candidate Mathematical Frameworks

Numerous mathematical approaches may satisfy these requirements to varying degrees.

Examples include:

Bayesian inference,
Dempster–Shafer belief theory,
probabilistic graphical models,
fuzzy logic,
certainty factor models,
graph-based reasoning,
neural confidence estimation,
hybrid reasoning systems.

Each framework provides different mechanisms for representing uncertainty while remaining compatible with the conceptual architecture described in this manuscript.

### 8.9.3 Bayesian Inference

Bayesian inference represents uncertainty through probability distributions that are updated as new evidence becomes available.

Within a Bayesian framework, prior beliefs are progressively refined through observed evidence to produce posterior probabilities describing the relative plausibility of competing hypotheses.

Bayesian reasoning provides several advantages:

mathematically rigorous,
incremental evidence updating,
well-established theoretical foundations,
extensive practical implementations.

However, Bayesian methods generally require explicit probabilistic assumptions and prior distributions that may be difficult to specify accurately for heterogeneous marketplace data.

Consequently, Bayesian inference represents one possible implementation of the Product Understanding Engine rather than its defining characteristic.

### 8.9.4 Dempster–Shafer Theory

Dempster–Shafer Theory extends classical probability by allowing reasoning under incomplete knowledge.

Rather than assigning probability directly to individual hypotheses, belief may be distributed across sets of hypotheses, explicitly representing uncertainty and ignorance.

This capability aligns naturally with several architectural principles developed throughout this manuscript, particularly:

incomplete evidence,
competing hypotheses,
deferred decision making,
explicit uncertainty.

Accordingly, Dempster–Shafer Theory represents an attractive implementation for reasoning in situations where available evidence remains incomplete.

### 8.9.5 Other Reasoning Frameworks

The architecture intentionally remains compatible with additional uncertainty models.

Examples include:

Probabilistic Graphical Models

Represent dependencies among numerous interacting variables.

Fuzzy Logic

Models approximate reasoning when concepts possess gradual rather than discrete boundaries.

Neural Confidence Estimation

Learns uncertainty directly from data without explicitly modelling probability.

Hybrid Systems

Combine deterministic rules, machine learning, probabilistic inference, and symbolic reasoning within a unified architecture.

Future advances in uncertainty modelling may also be incorporated without modifying the conceptual foundations of the Product Understanding Engine.

### 8.9.6 Why the Architecture Avoids Commitment

One of the primary design objectives of the Product Understanding Engine is long-term adaptability.

Scientific understanding evolves.

Machine learning evolves.

Reasoning algorithms evolve.

The conceptual architecture should remain stable despite these developments.

By separating architectural principles from mathematical implementation, the Product Understanding Engine enables future reasoning frameworks to replace existing implementations while preserving explainability, interoperability, and conceptual consistency.

This separation significantly increases the longevity of the architecture.

### 8.9.7 Choosing an Implementation

The selection of a particular uncertainty model should ultimately depend upon empirical evaluation rather than theoretical preference alone.

Factors influencing implementation choice include:

predictive accuracy,
computational efficiency,
scalability,
explainability,
robustness to noisy observations,
handling of incomplete information,
ease of maintenance.

The architecture therefore encourages evidence-based evaluation of competing mathematical frameworks rather than assuming a universally optimal solution.

### 8.9.8 Design Characteristics

The uncertainty modelling framework possesses several defining characteristics:

Architecture-first – Mathematical models implement rather than define reasoning.
Framework-agnostic – Multiple uncertainty models are supported.
Evidence-driven – All reasoning originates from structured evidence.
Future-proof – New mathematical methods may be incorporated without architectural redesign.
Scientifically rigorous – Implementation choices are validated empirically rather than assumed.

# Chapter 9 — Learning and Continuous Improvement

## 9.1 Introduction

The Product Understanding Engine must improve as products, terminology, providers, and failure patterns change. However, improvement must not allow unverified feedback or one unusual case to rewrite live behaviour.

Learning is therefore a controlled architectural process. Production outcomes create information for investigation, but they do not directly modify released models, rules, thresholds, or Knowledge Artifacts.

The governing path is:

    Decisions, failures, reviews, and downstream feedback
                        ↓
                  Learning Record
                        ↓
                  Change Candidate
                        ↓
          Offline implementation and evaluation
                        ↓
             Approval or rejection decision
                        ↓
             Released Capability Version
                        ↓
                Future live reasoning

Historical Decisions and their original reasoning remain immutable. This chapter defines how the PUE learns while preserving reproducibility, rollback, and product safety.

## 9.2 Learning as an Architectural Capability

Learning within the Product Understanding Engine extends beyond the training of machine learning models.

Instead, learning encompasses every mechanism through which the system acquires, validates, and incorporates new knowledge.

Learning may therefore occur through:

additional labelled data,
human feedback,
corrected product identifications,
improved evidence extraction,
refined reasoning strategies,
updated product catalogues,
revised confidence calibration,
improved retrieval mechanisms.

The architecture consequently views learning as a system-wide process rather than an isolated model update.

### 9.2.1 Separation of Reasoning and Learning

A fundamental architectural principle is the separation between live reasoning and controlled learning.

Live reasoning asks:

> What is the best justified Decision using the released capabilities and knowledge available for this case?

Learning asks:

> What recurring failure or opportunity should be converted into an evaluated change for future releases?

A completed case may create Feedback, a Review Record, a Correction, or a Learning Record. It must not directly alter production rules, weights, models, prompts, thresholds, or catalogue records.

### 9.2.2 Continuous Rather Than Static Improvement

The architecture supports continuous discovery of improvement opportunities, but production change remains versioned and gated.

Every processed case may reveal:

- a previously unseen product variant;
- a recurring extraction failure;
- a retrieval miss;
- a calibration problem;
- an incorrect product-form Decision;
- a missing or incorrect knowledge relationship.

These observations may create or strengthen a Learning Record. Only an evaluated and approved Change Candidate becomes part of a future Released Capability Version.

### 9.2.3 Learning Occurs Across Multiple Layers

Learning is not confined to a single architectural component.

Instead, improvement may occur throughout the Product Understanding Engine.

Examples include:

observation improvements,
OCR model refinement,
computer vision updates,
evidence quality calibration,
hypothesis generation,
candidate retrieval,
confidence estimation,
decision thresholds.

Each component may evolve independently while preserving the overall architectural framework.

### 9.2.4 Learning Preserves Explainability

Continuous improvement must not compromise explainability.

Whenever learning modifies system behaviour, the reasons for those modifications should remain understandable and traceable.

Consequently, the architecture records:

what changed,
why it changed,
what evidence motivated the change,
how performance was affected.

Learning therefore remains observable rather than opaque.

### 9.2.5 Design Characteristics

The learning architecture possesses several defining properties:

Continuous – Improvement occurs throughout system operation.
System-wide – Multiple architectural components may evolve.
Explainable – Learning decisions remain traceable.
Technology-independent – Compatible with numerous learning algorithms.
Evidence-driven – Improvements originate from accumulated operational experience.

## 9.3 Feedback Architecture

### 9.3.1 Introduction

Learning within the Product Understanding Engine is driven by feedback. Every improvement to the system originates from information describing how previous reasoning compared with reality. Consequently, feedback represents the primary mechanism through which operational experience is transformed into architectural improvement.

Rather than viewing feedback as a single event, the Product Understanding Engine treats feedback as a structured flow of information that may originate from multiple independent sources. These sources vary in reliability, completeness, and timeliness, but each contributes to the system's long-term understanding of product identification.

Accordingly, the architecture defines a unified Feedback Architecture responsible for collecting, evaluating, and incorporating information about system performance.

### 9.3.2 Sources of Feedback

Feedback may originate from numerous operational and external sources.

Examples include:

Human review and correction.
Validated catalogue updates.
Marketplace revisions.
Customer corrections.
Inventory reconciliation.
Model disagreement.
Downstream task outcomes.
Newly available product information.

Each source contributes evidence about the quality of previous reasoning rather than replacing that reasoning directly.

### 9.3.3 Explicit and Implicit Feedback

The architecture distinguishes between two broad categories of feedback.

Explicit Feedback

Explicit feedback occurs when an external authority directly identifies the correctness of a previous decision.

Examples include:

A human reviewer corrects a product identification.
A manufacturer publishes updated specifications.
A validated barcode mapping provides strong additional support for the product identity.

Explicit feedback generally possesses high reliability because the correction is intentional and directly observed.

Implicit Feedback

Implicit feedback is inferred indirectly from system behaviour or subsequent observations.

Examples include:

Multiple future observations consistently disagree with a previous identification.
Later evidence supports an alternative hypothesis.
Confidence repeatedly proves poorly calibrated.
Certain extraction failures occur systematically.

Implicit feedback may be weaker than explicit feedback but often occurs at much greater scale.

The architecture therefore supports both forms of learning.

### 9.3.4 Feedback as a Controlled Input

Feedback is a first-class object with provenance, source, reliability, supporting information, and verification status.

Feedback is not automatically ground truth and does not automatically become Evidence supporting a factual product Claim. It may:

- trigger review of a Decision;
- support a Correction or Superseding Decision;
- contribute to a Learning Record;
- identify a possible knowledge or capability defect.

Where feedback supplies new factual source material, that material may be admitted as a new Observation and processed through the normal Evidence and Claim pipeline.

### 9.3.5 Feedback Lifecycle

Every feedback event follows a controlled lifecycle:

    Feedback received
            ↓
    Source and reliability assessment
            ↓
    Case correction or adjudication, where justified
            ↓
    Learning Record creation or update
            ↓
    Change Candidate
            ↓
    Offline evaluation and regression testing
            ↓
    Approved release or rejection

A verified correction may supersede the Decision for that individual case immediately. It still does not modify general production behaviour until the broader change has passed evaluation and release approval.

### 9.3.6 Multiple Feedback Timescales

Learning activities may occur on different timescales without bypassing control.

**Immediate case correction**
A reviewer may issue a Superseding Decision for one case while preserving the automated Decision.

**Short-cycle capability improvement**
Rules, aliases, thresholds, retrieval configuration, or calibration may be proposed and evaluated against regression data.

**Long-cycle model or knowledge improvement**
Models may be retrained and Knowledge Artifacts rebuilt using versioned datasets and controlled release procedures.

The speed of the cycle may vary. The requirement for evaluation, versioning, and rollback does not.

### 9.3.7 Architectural Implications

A unified feedback architecture provides several important advantages.

It enables the Product Understanding Engine to:

learn from experience,
preserve explainability,
validate corrections,
distinguish reliable from unreliable feedback,
improve continuously,
support both automated and human-guided learning.

By treating feedback as a provenance-bearing input to review and learning rather than automatic truth, the architecture protects both reasoning integrity and controlled improvement.

### 9.3.8 Design Characteristics

The Feedback Architecture possesses several defining properties:

Provenance-driven – Feedback retains its source, reliability, support, and verification status.
Validated – Corrections are evaluated before influencing learning.
Multi-source – Supports diverse origins of feedback.
Multi-timescale – Enables both rapid and gradual improvement.
Explainable – Every learning event remains traceable to its originating feedback.

## 9.4 Hierarchical Expert Review

### 9.4.1 Introduction

Although the Product Understanding Engine is designed to reason autonomously, some observations will remain insufficiently resolved after the primary reasoning process. Rather than assuming that all uncertainty requires human intervention, the architecture permits unresolved observations to be escalated through a hierarchy of increasingly specialised reviewers.

These reviewers may include specialised reasoning modules, large language models, external expert systems, or human experts. Each reviewer contributes additional reasoning capability while preserving the evidence-based principles established throughout this manuscript.

The objective of hierarchical expert review is not to maximise human involvement, but to maximise the probability of accurate product identification while minimising unnecessary computational and human effort.

Consequently, the Product Understanding Engine treats expert review as an extension of its reasoning architecture rather than a failure of automation.

### 9.4.2 The Role of Expert Review

Expert review provides reasoning capabilities that complement the Product Understanding Engine when available Evidence remains insufficient for confident autonomous decision making.

Examples include:

identifying previously unseen products,
recognising marketplace-specific conventions,
interpreting complex or inconsistent product descriptions,
resolving ambiguous listings,
distinguishing complete products from accessories or components,
correcting systematic extraction errors,
validating unusual product variants,
detecting fraudulent or misleading listings.

Expert review may be performed by:

specialised AI modules,
external large language models,
locally hosted reasoning models,
human domain experts where appropriate.

Regardless of its source, expert reasoning is incorporated as structured Evidence within the broader architectural framework.

### 9.4.3 Hierarchical Escalation

The Product Understanding Engine employs a hierarchical escalation strategy in which increasingly capable reasoning systems are consulted only when required.

Routine observations that achieve sufficiently high confidence are resolved autonomously by the Product Understanding Engine.

Observations that remain uncertain may be escalated to progressively more capable expert reviewers.

A conceptual escalation pathway is illustrated below:

Marketplace Observation
        ↓
Product Understanding Engine
        ↓
High Confidence?
      /        \
    Yes        No
     │          │
Decision   Specialist Expert
                │
         High Confidence?
             /      \
           Yes      No
            │        │
       Decision   General LLM
                     │
             High Confidence?
                 /      \
               Yes      No
                │        │
          Decision   Unknown /
                   Deferred /
                Human Review (Optional)

This hierarchy enables computational resources to be allocated efficiently while ensuring that increasingly sophisticated reasoning is available when required.

### 9.4.4 Unknown is a Valid Outcome

The Product Understanding Engine does not assume that every observation must ultimately be resolved.

If all available reasoning systems remain unable to identify a product with sufficient confidence, the architecture permits the observation to remain unresolved.

Possible outcomes therefore include:

accepted identification,
deferred identification,
unknown product,
future review following additional Evidence.

Treating "unknown" as an explicit architectural outcome prevents unreliable decisions from being forced when available Evidence is insufficient.

This principle reflects the broader philosophy established throughout the architecture: uncertainty should be represented explicitly rather than concealed through unjustified confidence.

### 9.4.5 Expert Review Produces Evidence

Expert review produces a Review Record and may produce Feedback, a Correction, an Override, an Adjudication, or a Superseding Decision.

A reviewer may also identify new factual source material. That material should be admitted as an Observation and processed normally rather than being treated as unquestionable Evidence solely because an expert supplied it.

Every review outcome should record:

- reviewer or reviewer type;
- information presented;
- conclusion and requested action;
- supporting source material;
- confidence and limitations;
- timestamp and provenance.

Human or model expertise improves the evidence base but does not erase earlier reasoning history.

### 9.4.6 Efficient Allocation of Expertise

Expert reasoning represents a valuable computational or organisational resource.

The architecture therefore seeks to minimise unnecessary escalation.

Typical situations warranting expert review include:

low-confidence reasoning,
conflicting Evidence,
previously unseen products,
disagreement between reasoning modules,
strategically important products,
systematic failure patterns.

As the Product Understanding Engine improves through experience, the proportion of observations requiring expert review should progressively decrease.

### 9.4.7 Expert Disagreement

Different expert systems may legitimately produce different conclusions.

For example:

a specialised vision model,
a large language model,
and a human reviewer

may each propose different Product Hypotheses when available Evidence is incomplete.

Rather than forcing immediate agreement, the architecture records competing expert assessments as additional Evidence.

Subsequent observations may strengthen one explanation while weakening others.

This behaviour preserves uncertainty while avoiding premature commitment to a single interpretation.

### 9.4.8 Architectural Implications

The Hierarchical Expert Review framework provides several important architectural advantages.

It enables the Product Understanding Engine to:

scale efficiently across large product volumes,
allocate computational resources intelligently,
incorporate increasingly sophisticated reasoning only when required,
preserve explainability,
support multiple expert technologies,
accommodate future reasoning systems without architectural redesign.

Consequently, expert review becomes an adaptive extension of the reasoning architecture rather than a manual exception process.

### 9.4.9 Design Characteristics

The Hierarchical Expert Review framework exhibits several defining properties:

Hierarchical – Expertise is applied progressively according to need.
Technology-independent – Expert reviewers may be human or artificial.
Evidence-based – Every expert assessment becomes structured Evidence.
Scalable – Routine observations remain fully autonomous.
Explainable – Escalation decisions and expert reasoning remain traceable.
Future-proof – New expert systems may be incorporated without modifying the underlying architecture.

## 9.5 Intelligent Learning Prioritisation

### 9.5.1 Introduction

The Product Understanding Engine may process millions of product observations during normal operation. Although every observation contains potentially useful information, not every observation contributes equally to improving future reasoning.

Attempting to learn from every processed product with equal priority would consume unnecessary computational resources while yielding diminishing returns. The architecture therefore introduces Intelligent Learning Prioritisation, a framework responsible for determining which observations possess the greatest potential to improve future system performance.

Rather than maximising the quantity of learning, the objective is to maximise the value of learning.

### 9.5.2 Why Learning Must Be Prioritised

Most observations encountered during normal operation represent familiar products that the Product Understanding Engine can identify confidently using existing knowledge.

Repeatedly learning from observations that provide little additional information offers limited benefit while increasing computational cost and storage requirements.

Conversely, a relatively small proportion of observations may reveal:

previously unseen products,
emerging marketplace trends,
systematic reasoning failures,
ambiguous product descriptions,
novel product variants,
changes in marketplace terminology,
weaknesses within existing knowledge.

These observations possess significantly greater learning value because they expose opportunities for improving future reasoning.

Consequently, the architecture seeks to identify observations that maximise expected knowledge gain rather than processing every observation identically.

### 9.5.3 Learning Value

The Product Understanding Engine introduces the concept of Learning Value, representing the expected benefit that an observation may provide to future reasoning.

Learning Value is an architectural concept rather than a fixed numerical quantity. Different implementations may estimate Learning Value using different computational techniques while preserving the same underlying objective.

Observations exhibiting high Learning Value are prioritised for further analysis, expert review, model refinement, or future training.

Observations exhibiting low Learning Value may simply contribute to operational statistics without triggering additional learning processes.

### 9.5.4 Characteristics of High Learning Value

Although implementation-specific scoring mechanisms may differ, observations with high Learning Value frequently exhibit one or more of the following characteristics:

high reasoning uncertainty,
conflicting Evidence,
disagreement between expert reviewers,
previously unseen products,
unusual combinations of product attributes,
low confidence classifications,
repeated systematic failures,
commercially important products,
rapidly changing marketplace behaviour.

These characteristics indicate that additional analysis is likely to improve future system performance.

### 9.5.5 Novelty

Novel observations frequently possess greater learning potential than observations representing already well-understood products.

Novelty may arise from:

new product releases,
previously unseen product categories,
unusual seller terminology,
emerging marketplace conventions,
previously unobserved product variants,
uncommon image presentations,
newly introduced accessories or bundles.

Novel observations therefore represent valuable opportunities for expanding the Product Understanding Engine's knowledge.

### 9.5.6 Information Gain

Not all observations contribute equal amounts of new information.

Some merely reinforce existing knowledge.

Others fundamentally improve the Product Understanding Engine's understanding of products, terminology, marketplace behaviour, or reasoning strategies.

The architecture therefore seeks observations expected to maximise Information Gain, enabling future reasoning to improve more rapidly while avoiding unnecessary repetition.

### 9.5.7 Cost-Aware Learning

Learning itself consumes computational resources.

Additional processing may involve:

expert review,
external reasoning systems,
model retraining,
database updates,
knowledge refinement,
quality assurance,
long-term storage.

Consequently, Intelligent Learning Prioritisation balances the expected benefit of additional learning against the associated computational and operational costs.

This principle enables scalable operation across very large product collections without sacrificing continual improvement.

### 9.5.8 Architectural Implications

The Intelligent Learning Prioritisation framework enables the Product Understanding Engine to allocate learning resources efficiently by concentrating effort where future improvements are most likely to occur.

Rather than treating every processed observation equally, the architecture continuously identifies observations that provide the greatest opportunity for expanding knowledge, improving reasoning, and increasing future confidence.

This selective approach supports continual improvement while maintaining computational efficiency at scale.

### 9.5.9 Design Characteristics

The Intelligent Learning Prioritisation framework exhibits several defining properties:

Selective – Learning effort is focused where it provides maximum benefit.
Resource-aware – Computational cost is balanced against expected improvement.
Evidence-driven – Prioritisation is guided by characteristics of available Evidence.
Adaptive – Learning priorities evolve as marketplace behaviour changes.
Technology-independent – Multiple prioritisation strategies may be employed.
Scalable – Supports continual learning across millions of product observations.

## 9.6 Learning Evaluation and Validation

### 9.6.1 Introduction

Continuous learning alone does not guarantee continuous improvement. New knowledge, updated reasoning strategies, or refined models may improve performance in some situations while inadvertently reducing performance in others.

Consequently, the Product Understanding Engine treats learning and validation as distinct architectural processes. Learning proposes modifications to the system's knowledge and reasoning capabilities, whereas validation determines whether those modifications genuinely improve overall performance.

The objective is not simply to maximise learning, but to ensure that every accepted improvement demonstrably enhances the Product Understanding Engine's ability to reason accurately, consistently, and reliably.

### 9.6.2 Why Validation is Necessary

Learning introduces change.

Every change carries both potential benefit and potential risk.

Examples include:

improved identification of newly released products,
reduced performance on previously well-understood products,
increased reasoning confidence without corresponding increases in accuracy,
introduction of systematic bias,
unexpected interactions between knowledge components.

Without validation, gradual degradation may occur despite continual learning activity.

The architecture therefore requires all significant learning outcomes to undergo evaluation before becoming part of operational reasoning.

### 9.6.3 Learning Objectives

Validation requires clearly defined objectives against which improvement can be measured.

Depending upon implementation, these objectives may include:

improved identification accuracy,
improved confidence calibration,
reduced uncertainty,
increased robustness,
improved explainability,
greater consistency across marketplaces,
reduced false product identifications,
reduced expert review requirements.

The architecture deliberately avoids prescribing fixed performance metrics, recognising that appropriate evaluation criteria depend upon deployment requirements.

### 9.6.4 Benchmark Evaluation

To determine whether learning has improved the system, proposed changes should be evaluated using representative benchmark observations that remain independent from the learning process itself.

These benchmark observations should reflect:

common marketplace listings,
rare product variants,
ambiguous listings,
incomplete product descriptions,
misleading listings,
previously unseen products,
difficult edge cases.

Using diverse evaluation datasets helps ensure that improvements generalise beyond the observations from which learning originated.

### 9.6.5 Calibration Assessment

Improvement should not be measured solely by identification accuracy.

The Product Understanding Engine should also evaluate whether reported confidence remains appropriately calibrated.

For example, observations assigned high confidence should generally exhibit correspondingly high identification accuracy, while observations associated with lower confidence should accurately reflect greater uncertainty.

Well-calibrated confidence improves trustworthiness, supports downstream decision-making, and enables more effective prioritisation of expert review.

### 9.6.6 Regression Prevention

Learning should not improve one aspect of reasoning while unintentionally degrading another.

The architecture therefore encourages evaluation procedures capable of detecting regressions across previously validated capabilities.

Examples include reductions in:

identification accuracy,
reasoning consistency,
calibration quality,
explainability,
robustness,
computational efficiency.

Regression monitoring helps preserve accumulated knowledge while supporting continual improvement.

### 9.6.7 Explainable Improvement

Learning should itself remain explainable.

Accepted improvements should be accompanied by sufficient information to understand:

what changed,
why the change occurred,
which observations motivated the change,
how improvement was measured,
which capabilities were affected.

Maintaining transparent records of system evolution supports scientific reproducibility, operational trust, and long-term maintainability.

### 9.6.8 Continuous Evaluation

Evaluation is not restricted to isolated training events.

As marketplace behaviour evolves, previously validated reasoning strategies may gradually become less effective.

The architecture therefore supports continuous evaluation during normal operation, enabling performance changes to be detected as new observations accumulate.

This ongoing assessment allows the Product Understanding Engine to identify emerging weaknesses before they significantly affect operational performance.

### 9.6.9 Architectural Implications

Separating learning from validation provides an important safeguard against uncontrolled system evolution.

Rather than assuming that every learned modification represents an improvement, the architecture requires evidence that proposed changes enhance future reasoning while preserving existing capabilities.

This principle promotes reliable continual improvement without sacrificing stability or explainability.

### 9.6.10 Design Characteristics

The Learning Evaluation and Validation framework exhibits several defining properties:

Evidence-based – Improvements are supported by measurable evidence.
Independent – Validation remains distinct from the learning process itself.
Robust – Regression detection protects previously acquired capabilities.
Explainable – Accepted improvements remain transparent and traceable.
Adaptive – Evaluation evolves alongside changing marketplace behaviour.
Technology-independent – Applicable across diverse learning implementations.

## 9.7 Continuous Knowledge Evolution

### 9.7.1 Introduction

The knowledge represented within the Product Understanding Engine is not static. Products are continually introduced, discontinued, renamed, bundled, and described using new marketplace terminology. Consequently, the knowledge required for accurate product understanding evolves throughout the operational lifetime of the system.

Rather than treating knowledge as a fixed resource established during development, the architecture views knowledge as a sequence of versioned Knowledge Artifacts. Continuous Knowledge Evolution provides the controlled mechanisms through which proposed changes are evaluated, approved, released, monitored, and, where necessary, rolled back.

### 9.7.2 Why Knowledge Must Evolve

Knowledge that accurately represents today's marketplace may become incomplete or outdated as products and marketplace behaviour change.

Examples include:

newly released products,
discontinued products,
revised manufacturer naming conventions,
evolving seller terminology,
emerging product categories,
changing bundle configurations,
marketplace-specific language,
newly observed product relationships.

Without continual evolution, reasoning performance would gradually decline despite otherwise effective learning mechanisms.

The architecture therefore assumes that knowledge evolution is an ongoing operational process rather than an occasional maintenance activity.

### 9.7.3 Knowledge Expansion

One aspect of knowledge evolution involves expanding the system's understanding through the incorporation of new concepts.

A Change Candidate for knowledge expansion may include:

previously unseen products,
additional product variants,
newly observed accessories,
new manufacturer information,
expanded product relationships,
richer attribute descriptions,
additional evidence sources.

Expansion increases the breadth of knowledge available to future reasoning while preserving compatibility with existing knowledge.

### 9.7.4 Knowledge Refinement

Not all evolution involves adding new information.

Existing knowledge may also become more accurate as additional Evidence accumulates.

Examples include:

correcting inaccurate product attributes,
refining product relationships,
improving confidence estimates,
clarifying ambiguous terminology,
strengthening previously uncertain hypotheses,
improving evidence quality assessments.

Knowledge refinement is implemented by creating a new candidate artifact, evaluating it, and releasing a new version rather than editing the live artifact in place.

### 9.7.5 Knowledge Deprecation

As marketplaces evolve, some knowledge may become obsolete.

Examples include:

discontinued products,
obsolete naming conventions,
outdated marketplace terminology,
deprecated manufacturer catalogues,
historical product bundles.

Rather than deleting obsolete knowledge, the architecture supports controlled deprecation.

Deprecated knowledge remains available for historical reasoning where appropriate while no longer influencing current reasoning unnecessarily.

This approach preserves historical explainability and prevents unnecessary loss of information.

### 9.7.6 Knowledge Versioning

Knowledge evolves over time.

The architecture requires versioned Knowledge Artifacts so that every Decision can be associated with the exact knowledge available at the time it was made.

Knowledge versioning supports:

reproducibility,
auditing,
rollback,
comparison between knowledge revisions,
historical analysis,
scientific evaluation.

Maintaining knowledge history ensures that continual evolution remains transparent and explainable.

### 9.7.7 Adaptation to Marketplace Evolution

Marketplace behaviour changes continuously.

Sellers introduce new terminology, abbreviations, pricing conventions, listing styles, and product descriptions.

The Product Understanding Engine therefore monitors operational observations for evidence of systematic marketplace evolution.

When persistent changes are detected, they create Learning Records and Change Candidates. Only approved artifact versions enter future live reasoning; previous versions remain available for reconstruction and rollback.

This adaptive capability enables the architecture to remain effective despite continual external change.

### 9.7.8 Architectural Implications

Continuous Knowledge Evolution transforms the Product Understanding Engine from a static product classifier into a continually adapting knowledge system.

Rather than requiring periodic redevelopment, the architecture supports gradual refinement through controlled expansion, correction, deprecation, and adaptation.

This enables long-term operational effectiveness while preserving explainability, consistency, and historical integrity.

### 9.7.9 Design Characteristics

The Continuous Knowledge Evolution framework exhibits several defining properties:

Continuous – Knowledge evolves throughout the operational lifetime of the system.
Adaptive – Evolution reflects changes within the marketplace.
Incremental – Existing knowledge is refined without unnecessary disruption.
Historically consistent – Previous knowledge remains available through versioning and deprecation.
Explainable – Knowledge evolution is transparent and traceable.
Technology-independent – Applicable regardless of implementation methodology.

## 9.8 Learning Governance

### 9.8.1 Introduction

Continuous learning enables the Product Understanding Engine to improve throughout its operational lifetime. However, unrestricted modification of knowledge, reasoning strategies, or learned models may reduce reliability, reproducibility, and trust.

The architecture therefore introduces Learning Governance, a framework responsible for ensuring that learning remains controlled, transparent, and accountable. Rather than allowing knowledge to evolve without oversight, Learning Governance establishes principles through which modifications are monitored, validated, recorded, and, where necessary, reversed.

Learning Governance ensures that continual improvement occurs within a disciplined architectural framework.

### 9.8.2 Why Governance is Necessary

Every accepted learning event changes the behaviour of the Product Understanding Engine.

Examples include:

introducing new product knowledge,
refining existing product relationships,
updating reasoning strategies,
recalibrating confidence estimates,
modifying expert review behaviour.

While these changes may improve performance, they also introduce the possibility of unintended consequences.

The architecture therefore requires mechanisms capable of ensuring that learning remains reliable throughout long-term operation.

### 9.8.3 Traceability

Every significant learning event should be traceable.

Traceability enables the Product Understanding Engine to record:

what changed,
why the change occurred,
which observations initiated the change,
which Evidence supported the modification,
when the modification occurred,
which version of the knowledge base was affected.

Maintaining complete traceability supports explainability, auditing, debugging, and scientific reproducibility.

### 9.8.4 Version Control

Knowledge and reasoning capabilities must evolve through controlled versions rather than live, uncontrolled modification.

Version control enables the architecture to:

compare successive knowledge states,
reproduce historical reasoning,
evaluate the impact of learning,
restore previous versions where necessary,
support long-term maintenance.

Versioned knowledge ensures that continual learning remains transparent rather than opaque.

### 9.8.5 Rollback

Not every learned modification will prove beneficial.

The architecture therefore supports rollback mechanisms capable of restoring previously validated knowledge when later evidence demonstrates that a modification has reduced system performance or introduced undesirable behaviour.

Rollback provides resilience while encouraging continual experimentation and improvement.

### 9.8.6 Monitoring

Learning should be continuously monitored following deployment.

Monitoring may identify:

unexpected reductions in performance,
changing marketplace behaviour,
increasing uncertainty,
shifts in confidence calibration,
systematic reasoning failures,
emerging product categories.

Continuous monitoring enables early detection of issues before they significantly affect operational performance.

### 9.8.7 Reproducibility

Architectural improvements should be reproducible.

Given identical observations, knowledge, and reasoning configuration, the Product Understanding Engine should produce behaviour that is consistent and explainable.

Reproducibility supports:

scientific evaluation,
debugging,
benchmarking,
comparative experimentation,
regulatory compliance where applicable.

### 9.8.8 Governance as an Architectural Principle

Learning Governance is not intended to restrict improvement. It prevents autonomous online changes from bypassing evaluation and release control.

Instead, it provides the architectural discipline necessary to ensure that learning remains trustworthy throughout the lifetime of the Product Understanding Engine.

By combining traceability, version control, monitoring, validation, and rollback, the architecture supports continual evolution without sacrificing stability or explainability.

### 9.8.9 Design Characteristics

The Learning Governance framework exhibits several defining properties:

Transparent – Learning activities remain visible and explainable.
Traceable – Every significant modification can be audited.
Version-controlled – Knowledge evolves through identifiable revisions.
Recoverable – Previous knowledge states can be restored.
Reliable – Monitoring protects against unintended degradation.
Technology-independent – Governance principles apply regardless of implementation.

## 9.9 Architectural Implications

### 9.9.1 Learning as a Continuous Architectural Capability

The Product Understanding Engine treats learning as a continuous architectural capability rather than a discrete training activity.

Traditional machine learning systems are often developed through periodic cycles of data collection, model training, deployment, and maintenance. In contrast, the Product Understanding Engine is designed to improve continuously through operational experience while preserving stability, explainability, and architectural consistency.

Learning therefore becomes an integral component of everyday reasoning rather than an isolated development process.

### 9.9.2 Separation of Reasoning and Learning

A fundamental architectural principle established throughout this chapter is the separation of reasoning from learning.

Reasoning seeks to determine the most plausible explanation for an individual observation using the knowledge currently available.

Learning seeks to improve the knowledge available for future reasoning.

Although closely related, these processes serve different objectives and operate over different timescales.

Maintaining this separation enables the architecture to improve continuously without compromising the consistency or explainability of operational reasoning.

### 9.9.3 Selective Improvement

The architecture recognises that not every observation contributes equally to future improvement.

Consequently, learning resources are allocated selectively according to the expected value of additional knowledge rather than uniformly across all processed observations.

This selective approach enables scalable continual learning while avoiding unnecessary computational expenditure.

Learning therefore becomes both adaptive and resource-aware.

### 9.9.4 Evidence-Centred Learning

Throughout the Product Understanding Engine, Evidence remains the fundamental representation from which reasoning, confidence, expert review, and learning are derived.

Expert assessments, operational feedback, validation results, and newly acquired information are represented through their appropriate objects—Review Records, Feedback, Evaluation Results, Observations, and Knowledge Artifacts—rather than being collapsed into one generic Evidence type.

This unified representation simplifies architectural design while ensuring consistency across the entire system.

### 9.9.5 Controlled Evolution

Continual improvement must remain compatible with long-term stability.

The Product Understanding Engine therefore combines learning with validation, governance, monitoring, and version control to ensure that accumulated knowledge evolves in a controlled and explainable manner.

Rather than pursuing unrestricted adaptation, the architecture emphasises trustworthy evolution supported by measurable evidence.

### 9.9.6 Long-Term Scalability

The architectural principles introduced throughout this chapter enable continual learning across very large product collections without requiring proportional increases in human intervention.

By combining autonomous reasoning, hierarchical expert review, intelligent learning prioritisation, continuous validation, knowledge evolution, and governance, the architecture supports sustained improvement throughout prolonged operational deployment.

This scalability is achieved through selective allocation of computational and organisational resources rather than indiscriminate application of increasingly complex algorithms.

### 9.9.7 Relationship to the Product Understanding Engine

Learning is a connected but operationally separate subsystem. It consumes outcomes from the Product Understanding Engine and produces evaluated releases for future reasoning.

Instead, it represents a complementary architectural capability that continually refines the knowledge, evidence, and reasoning processes upon which product understanding depends.

The Product Understanding Engine therefore improves not by replacing its reasoning mechanisms, but by continually strengthening the knowledge and Evidence that support those mechanisms.

### 9.9.8 Design Characteristics

The Learning Architecture exhibits several defining properties:

Continuous – Learning occurs throughout the operational lifetime of the system.
Evidence-centred – Learning is driven by structured Evidence.
Selective – Resources are allocated according to expected learning value.
Explainable – Improvements remain transparent and reproducible.
Governed – Evolution occurs within a controlled architectural framework.
Scalable – Continuous improvement supports operation across millions of product observations.
Technology-independent – The architecture remains independent of specific machine learning techniques.

## 9.10 Chapter Summary

This chapter introduced the learning architecture of the Product Understanding Engine. Rather than treating learning as an isolated model training activity, the architecture presents continual improvement as an integrated capability that operates throughout the system's lifetime.

The chapter established principles for feedback acquisition, hierarchical expert review, intelligent learning prioritisation, evaluation and validation, continuous knowledge evolution, and learning governance. Collectively, these components enable the Product Understanding Engine to improve through operational experience while preserving explainability, stability, and architectural consistency.

A central theme throughout the chapter has been that learning should not maximise the quantity of accumulated knowledge, but rather the quality and usefulness of that knowledge. By selectively acquiring, validating, governing, and integrating new information, the architecture supports sustained improvement without sacrificing reliability or transparency.

The resulting learning framework complements the evidence-centred reasoning architecture developed in previous chapters and provides the foundation for long-term adaptation within dynamic marketplace environments.

# Chapter 10 — System Architecture

## 10.1 Introduction

The preceding chapters established the conceptual foundations of the Product Understanding Engine (PUE). They described how marketplace information is transformed into structured Observations, Evidence, Claims, Product Hypotheses, Candidate Products, and ultimately evidence-based product decisions. Together, these components define the reasoning process underlying product understanding.

This chapter integrates those concepts into a unified system architecture. Rather than introducing new reasoning methods, it describes how the major architectural components interact to transform raw marketplace listings into structured, explainable product identifications.

The PUE is organised as a layered, modular architecture in which each component performs a well-defined responsibility while exchanging information through stable interfaces. This separation of concerns allows individual components to evolve independently without requiring changes to the overall architecture. For example, extraction models, retrieval algorithms, reasoning engines, or learning methods may be replaced as technology advances while preserving the conceptual workflow established throughout this manuscript.

The architecture is intentionally technology-independent. It defines the responsibilities, information flow, and interactions between components rather than prescribing specific implementation techniques. This enables the PUE to incorporate future advances in artificial intelligence, information retrieval, probabilistic reasoning, and machine learning without fundamental architectural redesign.

The remainder of this chapter presents the overall architecture, describes the principal architectural layers, explains the flow of information through the system, and outlines the design principles that support scalability, explainability, extensibility, and long-term evolution.

## 10.2 Architectural Overview

The Product Understanding Engine (PUE) is organised as a layered, modular architecture that transforms unstructured marketplace listings into structured, explainable product identifications. Each layer performs a distinct responsibility, progressively enriching the available information while preserving complete traceability to the original marketplace observations.

The architecture follows a sequential reasoning pipeline in which each processing stage consumes the outputs of the previous stage while producing richer, more structured representations for subsequent reasoning. This separation of concerns improves modularity, simplifies implementation, and allows individual components to evolve independently without affecting the overall system architecture.

At a high level, the PUE consists of six principal architectural layers:

Data Acquisition Layer – Collects marketplace listings and extracts raw textual, visual, and metadata observations.
Knowledge Representation Layer – Transforms observations into structured Evidence and Claims that describe individual product characteristics.
Reasoning Layer – Generates Product Hypotheses, retrieves Candidate Products, and evaluates competing explanations using the available Evidence.
Decision Layer – Determines whether sufficient evidence exists to identify a canonical product or whether uncertainty should be preserved.
Learning Layer – Converts feedback and failures into Learning Records and Change Candidates, evaluates proposed improvements, and releases approved versions with governance and traceability.
Knowledge Base – Maintains versioned known-product records, domain knowledge, relationships, provenance, and coverage information used throughout retrieval and reasoning.

Conceptually, the architecture can be represented as:

Marketplace Listings
          │
          ▼
Data Acquisition
          │
          ▼
Observations
          │
          ▼
Evidence & Claims
          │
          ▼
Product Hypotheses
          │
          ▼
Candidate Retrieval
          │
          ▼
Candidate Evaluation
          │
          ▼
Decision Readiness
          │
          ▼
Product Decision
          │
          ▼
Learning & Knowledge Evolution

Although illustrated as a sequential pipeline, the architecture supports iterative reasoning. Later stages may generate additional evidence, refine existing hypotheses, or trigger further analysis before a final decision is reached. This feedback capability enables the PUE to reason under uncertainty while preserving explainability and adaptability.

Each architectural layer exposes well-defined interfaces and exchanges structured information rather than implementation-specific data structures. As a result, new extraction models, reasoning algorithms, retrieval strategies, or learning methods can be incorporated without requiring changes to the surrounding architecture. This modular design ensures that the PUE remains scalable, maintainable, and capable of incorporating future advances in artificial intelligence and product understanding.

## 10.3 Architectural Layers

The Product Understanding Engine is organised into a series of logical architectural layers, each responsible for a distinct stage of product understanding. This separation of concerns improves modularity, maintainability, and scalability while allowing individual components to evolve independently.

### 10.3.1 Data Acquisition Layer

The Data Acquisition Layer receives raw marketplace listings and extracts all available information, including textual descriptions, images, metadata, identifiers, and other observable characteristics. Its responsibility is to transform heterogeneous marketplace data into structured Observations suitable for further processing.

### 10.3.2 Knowledge Representation Layer

The Knowledge Representation Layer converts Observations into structured Evidence and Claims. This layer establishes the common information model used throughout the architecture, ensuring that subsequent reasoning operates on consistent, explainable representations rather than raw marketplace data.

### 10.3.3 Reasoning Layer

The Reasoning Layer performs the core product understanding process. It generates Product Hypotheses, retrieves Candidate Products from the Canonical Product Knowledge Base, evaluates competing explanations, and progressively refines product understanding using the available Evidence.

### 10.3.4 Decision Layer

The Decision Layer determines whether the available Evidence justifies selecting a canonical product. Rather than always producing a definitive result, it may accept a candidate, defer the decision, preserve ambiguity, or reject all candidates when the available Evidence is insufficient.

### 10.3.5 Learning Layer

The Learning Layer continuously improves the system by incorporating validated knowledge derived from previous decisions, expert review, and new marketplace observations. Learning operates independently of the reasoning process, allowing knowledge to evolve without compromising system stability.

### 10.3.6 Knowledge Base

The Canonical Product Knowledge Base provides versioned reference knowledge used throughout the architecture. It stores versioned known-product records, domain knowledge, validated relationships, and supporting information required for retrieval and reasoning. Its limitations and coverage must remain explicit.

Layer Independence

Although the layers operate cooperatively, each exposes well-defined responsibilities and interfaces. This modular organisation allows individual layers to be improved, replaced, or extended without requiring changes to the remainder of the architecture. Consequently, advances in extraction methods, reasoning algorithms, retrieval techniques, or learning approaches can be incorporated while preserving the overall architectural design.

## 10.4 Information Flow

The Product Understanding Engine processes each marketplace listing through a structured sequence of transformations that progressively convert unstructured data into an explainable product identification. At each stage, information becomes more structured while maintaining complete traceability to the original marketplace observations.

The processing workflow begins with the acquisition of a marketplace listing. Text, images, metadata, identifiers, and other available information are collected and transformed into structured Observations.

These Observations are analysed to produce Evidence, which captures individual pieces of information together with their provenance, quality, and confidence. Evidence is then interpreted as structured Claims describing product characteristics such as manufacturer, model, specifications, condition, or included accessories.

The Reasoning Layer combines compatible Claims into one or more Product Hypotheses representing plausible interpretations of the listing. Each hypothesis is used to retrieve Candidate Products from the Canonical Product Knowledge Base, after which the candidates are evaluated according to how completely and consistently they explain the available Evidence.

Following candidate evaluation, the Decision Layer determines whether sufficient Evidence exists to identify a canonical product. Where appropriate, the engine may defer the decision, preserve multiple competing candidates, or reject all candidates if the available Evidence does not adequately support any known product.

Finally, Decisions and validated feedback enter the Learning Layer, where they may create Learning Records and Change Candidates. Proposed changes are evaluated and released separately without altering the completed reasoning process.

The overall information flow can be summarised as follows:

Marketplace Listing
        │
        ▼
Data Acquisition
        │
        ▼
Observations
        │
        ▼
Evidence
        │
        ▼
Claims
        │
        ▼
Product Hypotheses
        │
        ▼
Candidate Retrieval
        │
        ▼
Candidate Evaluation
        │
        ▼
Decision Readiness
        │
        ▼
Product Decision
        │
        ▼
Learning & Knowledge Evolution

This structured information flow separates acquisition, representation, reasoning, decision making, and learning into distinct architectural stages while preserving complete explainability throughout the product understanding process. Each stage operates on well-defined inputs and outputs, enabling individual components to evolve independently without affecting the overall system architecture.

## 10.5 Component Interactions

The Product Understanding Engine is composed of loosely coupled components that communicate through well-defined interfaces. Each component performs a specific responsibility and exchanges structured information rather than implementation-specific data structures. This separation enables individual components to be developed, tested, and replaced independently while preserving the overall system architecture.

Information flows sequentially through the architecture, with each component consuming the outputs of the preceding stage and producing structured inputs for the next. Components do not require knowledge of the internal implementation of other modules, relying instead on the shared architectural representations established throughout this manuscript.

The principal interactions between components are:

The Data Acquisition Layer produces structured Observations.
The Knowledge Representation Layer transforms Observations into Evidence and Claims.
The Reasoning Layer generates Product Hypotheses and retrieves Candidate Products from the Canonical Product Knowledge Base.
The Candidate Evaluation component evaluates retrieved products using the complete body of available Evidence.
The Decision Layer determines whether sufficient Evidence exists to produce a product identification.
The Learning Layer converts validated outcomes and feedback into Learning Records and Change Candidates. Only evaluated Released Capability Versions influence future live reasoning.

The Canonical Product Knowledge Base interacts with multiple architectural layers. It provides versioned known-product records during Candidate Retrieval and domain knowledge during reasoning. Proposed updates enter only through the controlled change-and-release process. This gives components a consistent reference while preserving the possibility that the knowledge is incomplete or wrong.

The interactions between components can be summarised as follows:

Marketplace Listing
        │
        ▼
Data Acquisition
        │
        ▼
Knowledge Representation
        │
        ▼
Reasoning
        │
        ├──────────────► Canonical Product Knowledge Base
        │                         ▲
        ▼                         │
Decision Layer                    │
        │                         │
        ▼                         │
Learning Layer ───────────────────┘

By defining clear interfaces and responsibilities, the architecture supports parallel development, simplifies testing, and enables individual components to evolve independently. This modular design also facilitates future extensions, allowing new extractors, reasoning methods, retrieval algorithms, or learning strategies to be incorporated without requiring fundamental changes to the surrounding architecture.

## 10.6 Architectural Principles

The Product Understanding Engine is founded upon a set of architectural principles that guide its design and ensure consistency across all components. These principles are independent of specific implementation technologies and provide the foundation for future evolution of the system.

The principal architectural principles are:

Evidence-centred – All reasoning is grounded in explicit Evidence derived from marketplace observations.
Hypothesis-driven – Product identification is performed by generating and evaluating competing Product Hypotheses rather than making immediate classifications.
Explainable – Every product decision can be traced through the complete chain of Observations, Evidence, Claims, and reasoning steps.
Modular – Components perform well-defined responsibilities and communicate through stable interfaces.
Technology-independent – The architecture specifies responsibilities and information flow rather than prescribing particular algorithms or models.
Scalable – The architecture supports large product catalogues, high-volume marketplace data, and distributed implementations.
Extensible – New extractors, reasoning methods, retrieval strategies, and learning techniques can be incorporated without redesigning the overall architecture.
Learning-oriented – Knowledge evolves through validated learning while preserving governance, traceability, and reproducibility.

Together, these principles ensure that the Product Understanding Engine remains robust, maintainable, and adaptable while supporting continual advances in artificial intelligence and product understanding technologies.

## 10.7 Extensibility

One of the primary strengths of the Product Understanding Engine is its extensible architecture. The system is designed to accommodate new capabilities without requiring fundamental changes to its core structure. This allows the PUE to evolve alongside advances in artificial intelligence, information retrieval, and marketplace technologies.

New components can be incorporated by extending existing architectural interfaces rather than modifying established workflows. For example, additional data extractors, computer vision models, large language models, retrieval algorithms, reasoning strategies, or learning methods may be integrated while preserving the overall information flow.

Similarly, the architecture supports expansion of the Canonical Product Knowledge Base to include new product categories, marketplaces, and domain-specific knowledge. Because reasoning operates on common architectural representations such as Observations, Evidence, Claims, and Product Hypotheses, these extensions remain compatible with existing components.

This modular approach simplifies maintenance, supports incremental development, and enables the PUE to adapt to future technologies without architectural redesign.

## 10.8 Chapter Summary

This chapter integrated the concepts developed throughout the preceding chapters into a unified system architecture for the Product Understanding Engine. It described the principal architectural layers, the flow of information through the system, the interactions between components, and the design principles that guide the architecture.

The resulting architecture provides a modular, evidence-centred, and hypothesis-driven framework for product understanding. By separating acquisition, knowledge representation, reasoning, decision making, and learning into distinct components, the PUE supports explainable reasoning, scalable implementation, and continual evolution while remaining independent of specific implementation technologies.

This architectural foundation provides the basis for the implementation considerations presented in the following chapter.

# Chapter 11 — Implementation Considerations

## 11.1 Introduction

The preceding chapters defined the conceptual architecture of the Product Understanding Engine (PUE). This chapter considers how that architecture may be implemented as a practical software system while remaining independent of specific technologies, programming languages, or artificial intelligence models.

The objective is not to prescribe a single implementation, but to demonstrate how the architectural concepts introduced throughout this manuscript can be realised as modular software components. By separating architectural responsibilities from implementation details, the PUE can evolve alongside advances in artificial intelligence, information retrieval, and software engineering without requiring fundamental redesign.

## 11.2 Mapping the Architecture to Software Components

The conceptual architecture described throughout this manuscript can be implemented as a collection of cooperating software components. Each architectural layer maps naturally to one or more software modules responsible for a clearly defined function.

A typical implementation may include components for:

Marketplace data acquisition.
Observation extraction.
Evidence and Claim generation.
Product Hypothesis generation.
Candidate Retrieval.
Candidate Evaluation.
Decision management.
Learning and knowledge management.
Canonical Product Knowledge Base management.

These components communicate through the architectural representations defined in earlier chapters, including Observations, Evidence, Claims, Product Hypotheses, Candidate Products, and Decisions. This shared information model allows individual modules to evolve independently while maintaining interoperability across the system.

## 11.3 Technology Independence

The Product Understanding Engine deliberately separates architectural responsibilities from implementation technologies. Throughout this manuscript, concepts such as Evidence, Product Hypotheses, Candidate Retrieval, and Learning describe functional responsibilities rather than specific algorithms.

Consequently, an implementation may employ a wide range of technologies, including deterministic rule systems, traditional information retrieval techniques, machine learning, probabilistic reasoning, graph databases, vector search, large language models, or hybrid approaches.

As new technologies emerge, individual components may be replaced or enhanced without altering the overall architecture, provided they continue to satisfy the interfaces and responsibilities defined by the PUE.

## 11.4 Scalability and Deployment

The architecture is designed to support implementations ranging from small research prototypes to large-scale production systems.

Individual components may be deployed as a single application, as modular services, or as distributed systems depending upon performance and operational requirements. Because components communicate through well-defined interfaces, computationally intensive processes such as image analysis, candidate retrieval, or learning can be scaled independently.

Similarly, the Canonical Product Knowledge Base may grow from a small experimental catalogue to millions of products spanning multiple marketplaces without requiring changes to the surrounding architecture.

The modular design therefore supports incremental scaling as both product coverage and processing volume increase.

## 11.5 Incremental Implementation Roadmap

The modular architecture of the Product Understanding Engine supports incremental implementation. Rather than requiring all capabilities to be developed simultaneously, the system can evolve through successive stages while preserving the overall architectural design.

A typical implementation roadmap may include:

Phase 1 – Core Product Identification

Implement marketplace data acquisition, Observation generation, Evidence and Claim construction, Product Hypothesis generation, Candidate Retrieval, and Decision management using a limited Canonical Product Knowledge Base.

Phase 2 – Enhanced Reasoning

Introduce richer Evidence extraction, multimodal analysis, improved retrieval methods, and more sophisticated candidate evaluation to increase accuracy and robustness.

Phase 3 – Controlled Learning and Review

Implement Feedback, Review Records, Learning Records, Change Candidates, offline evaluation, release approval, and rollback to enable controlled improvement over time.

Phase 4 – Large-Scale Deployment

Expand the Canonical Product Knowledge Base, support multiple marketplaces and product categories, optimise scalability, and incorporate distributed processing where appropriate.

This staged approach enables useful functionality to be delivered early while allowing progressively more advanced capabilities to be integrated without architectural redesign.

## 11.6 Chapter Summary

This chapter demonstrated how the conceptual architecture presented throughout this manuscript can be realised as a practical software system. By mapping architectural concepts to modular software components, maintaining technology independence, supporting scalable deployment, and adopting an incremental implementation strategy, the Product Understanding Engine provides a practical foundation for real-world development.

The next chapter considers how such an implementation can be evaluated to assess its accuracy, explainability, robustness, scalability, and continual learning performance.

# Chapter 12 — Evaluation Framework

## 12.1 Introduction

A successful Product Understanding Engine must not only identify products accurately but also demonstrate that its decisions are reliable, explainable, and robust under real-world conditions. Consequently, evaluation extends beyond measuring classification accuracy alone.

This chapter presents a framework for evaluating the PUE across multiple dimensions, reflecting the evidence-centred and hypothesis-driven architecture developed throughout this manuscript. The framework is intended to guide both research evaluation and practical system validation while remaining independent of specific implementation technologies.

## 12.2 Evaluation Objectives

The evaluation framework should determine whether the PUE produces useful, safe, and operationally viable product understanding.

Evaluation should cover:

- Evidence and Claim correctness;
- Candidate Retrieval recall;
- Candidate Evaluation quality;
- exact and hierarchical identification accuracy;
- product-form accuracy;
- contradiction retention;
- over-specific and under-specific Decisions;
- abstention and selective-prediction behaviour;
- confidence calibration at defined targets;
- Explanation faithfulness;
- throughput, latency, resource use, and cost;
- downstream comparability and commercial-error prevention;
- stability of controlled learning releases.

A correct unsupported answer is not complete success, and a safe partial identification may be more useful than an exact but incorrect match.

## 12.3 Accuracy Evaluation

Accuracy evaluation should reflect the hierarchy and consequences of product understanding rather than use exact match alone.

It should measure:

- exact known-product accuracy;
- family, model, and variant accuracy;
- product-form accuracy;
- Candidate recall at defined values of *k*;
- compatibility-versus-identity errors;
- accessory-versus-complete-product errors;
- harmful false-match rate;
- avoidable abstention rate;
- failures to abstain;
- performance by provider, category, language, processing lane, and source quality.

The evaluation dataset should include ambiguous listings, catalogue gaps, packaging-only cases, bundles, accessories, copied descriptions, and text–image contradictions.

## 12.4 Explainability Evaluation

Because explainability is a central architectural principle, evaluation should assess not only whether the correct decision was reached but also whether the reasoning process can be understood and verified.

Evaluation should therefore consider:

Traceability from decisions to Observations.
Completeness of Evidence and Claim provenance.
Transparency of Product Hypothesis generation.
Interpretability of candidate evaluation.
Clarity of decision explanations.

An explainable system enables both developers and users to understand how conclusions were reached and to identify sources of error when incorrect decisions occur.

## 12.5 Robustness Evaluation

The Product Understanding Engine should maintain reliable performance when processing incomplete, ambiguous, or inconsistent marketplace listings. Evaluation should therefore assess the system's ability to reason effectively despite missing information, conflicting evidence, poor-quality images, inaccurate metadata, and other real-world imperfections.

Robustness should be measured across diverse marketplaces, product categories, and listing qualities to ensure consistent performance under practical operating conditions.

## 12.6 Scalability Evaluation

The architecture is intended to support large product catalogues and high-volume marketplace data. Evaluation should therefore assess the ability of the system to maintain acceptable performance as the number of marketplace listings, canonical products, and concurrent processing tasks increases.

Typical evaluation measures may include processing throughput, retrieval performance, resource utilisation, and response time under increasing workload.

## 12.7 Learning Evaluation

Continual learning should improve system performance without compromising stability or explainability. Evaluation should therefore assess whether learning produces measurable improvements while preserving existing knowledge and reasoning quality.

Representative evaluation criteria include:

Improvement in product identification accuracy.
Calibration of defined confidence dimensions and Decision confidence at the stated identification level.
Stability across successive learning cycles.
Resistance to performance regression.
Effectiveness of knowledge evolution.

Learning should be regarded as successful only when validated improvements are consistently demonstrated.

## 12.8 Overall System Evaluation

Because the Product Understanding Engine integrates multiple architectural components, evaluation should consider overall system performance rather than isolated module performance. End-to-end evaluation assesses how effectively the complete architecture transforms marketplace listings into accurate, explainable product identifications.

Accordingly, system evaluation should combine measures of accuracy, explainability, robustness, scalability, and learning performance to provide a comprehensive assessment of operational effectiveness.

## 12.9 Chapter Summary

This chapter presented a framework for evaluating the Product Understanding Engine across the principal dimensions of system performance. By considering accuracy, explainability, robustness, scalability, and continual learning, the framework provides a comprehensive basis for assessing both research implementations and production deployments.

The following chapter discusses the limitations of the proposed architecture and identifies opportunities for future research and development.

# Chapter 13 — Limitations and Future Research

## 13.1 Introduction

Although the Product Understanding Engine provides a comprehensive architecture for evidence-based product understanding, no architecture can completely eliminate the challenges associated with real-world marketplace data. This chapter discusses the principal limitations of the proposed approach and identifies directions for future research that may further improve system capability.

## 13.2 Current Limitations

Several practical limitations remain.

Marketplace listings may contain insufficient information to uniquely identify a product. Canonical product catalogues may be incomplete or contain outdated information. Emerging products, novel product variants, and rapidly changing marketplace terminology may reduce identification performance until the knowledge base is updated.

Furthermore, the quality of reasoning remains dependent upon the quality of the available observations and evidence. Incorrect or incomplete inputs may limit the accuracy of subsequent reasoning despite the architecture's ability to manage uncertainty.

## 13.3 Future Research

Future research may investigate improved multimodal reasoning, richer knowledge representations, enhanced retrieval methods, controlled automated knowledge acquisition, advanced continual learning strategies, and more sophisticated reasoning algorithms.

Additional research may also explore larger canonical product knowledge bases, broader marketplace coverage, improved handling of previously unseen products, and tighter integration with emerging artificial intelligence technologies.

# Chapter 14 — Conclusion

## 14.1 Summary of Contributions

This manuscript presented the Product Understanding Engine (PUE), a conceptual architecture for transforming unstructured marketplace listings into structured, explainable product identifications. Rather than treating product identification as a single classification task, the PUE models it as an evidence-centred reasoning process that progressively transforms marketplace observations into product decisions through structured knowledge representation, hypothesis generation, candidate retrieval, evidence-based evaluation, and continual learning.

The architecture emphasises modularity, explainability, technology independence, and scalability, enabling future advances in artificial intelligence and information retrieval to be incorporated without requiring fundamental architectural redesign.

## 14.2 Architectural Significance

The principal contribution of the Product Understanding Engine is the integration of knowledge representation, evidence-based reasoning, hypothesis-driven inference, explainable decision making, and continual learning within a unified architectural framework.

By separating acquisition, representation, reasoning, decision making, and learning into distinct architectural components, the PUE provides a structured foundation for building intelligent product understanding systems capable of operating across diverse marketplaces and evolving product catalogues.

## 14.3 Future Outlook

Marketplace data will continue to increase in volume, complexity, and diversity. At the same time, advances in multimodal artificial intelligence, large language models, retrieval systems, and continual learning will expand the capabilities available to product understanding systems.

The architecture proposed in this manuscript is intended to provide a stable conceptual foundation capable of accommodating these developments while preserving explainability, robustness, and long-term maintainability.

## 14.4 Closing Remarks

Accurate product understanding is a fundamental requirement for many digital commerce applications, including marketplace search, inventory management, pricing, recommendation, digital arbitrage, and automated product analysis. As marketplace ecosystems continue to evolve, systems must move beyond isolated predictions towards architectures capable of reasoning explicitly about uncertainty, evidence, and competing explanations.

The Product Understanding Engine provides one possible foundation for this transition. By placing evidence, explainability, and structured reasoning at the centre of the architecture, it offers a practical framework for developing intelligent product understanding systems that are both scientifically grounded and suitable for real-world implementation.


# Appendix A — Reference Architecture

## A.1 Purpose

The preceding chapters describe the Product Understanding Engine (PUE) from an architectural and conceptual perspective. They define the principles, reasoning processes, and system responsibilities required to perform robust product understanding while remaining independent of any particular implementation technology.

This appendix complements the main manuscript by presenting a technology-independent reference architecture. Rather than prescribing specific algorithms, programming languages, databases, or machine learning models, it defines the core architectural objects, their relationships, and the contracts that exist between the principal components of the system.

The purpose of this appendix is not to provide an implementation specification. Instead, it establishes a common architectural vocabulary that enables independent implementations of the PUE while preserving the reasoning principles described throughout the manuscript. The reference architecture therefore serves as a bridge between the conceptual framework presented in the main body of the work and future software implementations.

By separating architectural responsibilities from implementation choices, the Product Understanding Engine remains adaptable to future advances in artificial intelligence, knowledge representation, computer vision, information retrieval, and machine learning. Alternative technologies may be substituted without altering the fundamental architecture provided that they satisfy the architectural contracts defined within this appendix.

Accordingly, this appendix should be regarded as a practical conceptual reference for the structural organisation of the Product Understanding Engine rather than a prescriptive software design. Individual implementations may differ substantially in their internal algorithms while remaining architecturally consistent with the principles established throughout this manuscript.

## A.2 Architectural Principles

The Product Understanding Engine (PUE) is founded upon a small number of architectural principles that remain invariant regardless of the implementation technologies employed. These principles define the structural organisation of the system rather than the algorithms used to realise its functionality.

First, product understanding is regarded as a reasoning process rather than a classification task. Every architectural component exists to progressively transform uncertain observations into increasingly reliable knowledge. The architecture therefore emphasises the accumulation, evaluation, and synthesis of evidence instead of direct prediction.

Second, information is treated as progressively refined representations rather than interchangeable data. Observations, evidence, claims, hypotheses, and decisions each represent distinct stages of reasoning with clearly defined responsibilities. Information flows between these stages through well-defined architectural contracts while preserving provenance and explainability.

Third, the architecture maintains strict separation between knowledge representation and reasoning mechanisms. The representation of products, observations, and evidence remains independent of the algorithms used to analyse them. Consequently, future advances in machine learning, symbolic reasoning, computer vision, or large language models may be incorporated without altering the underlying architectural structure.

Fourth, every decision produced by the Product Understanding Engine must be explainable. Conclusions are not treated as opaque predictions but as reasoned outcomes derived from identifiable evidence. At every stage of the reasoning pipeline, the architecture preserves sufficient information to reconstruct how a particular conclusion was reached.

Finally, the architecture is intentionally technology independent. No component assumes the use of a particular database, programming language, machine learning model, search engine, or software framework. Any implementation satisfying the architectural responsibilities and contracts described within this appendix may be considered a valid implementation of the Product Understanding Engine.

## A.3 Core Architectural Objects

The Product Understanding Engine is composed of a small number of fundamental architectural objects. These objects represent the stable conceptual entities that exist throughout the reasoning process. While individual implementations may choose different internal representations, the architectural responsibilities of these objects remain constant.

Observation

An Observation represents a single piece of information acquired from an external source. Observations constitute the lowest level of architectural knowledge and are considered immutable once created. They contain only directly observed information and make no attempt to interpret or infer meaning.

Examples include textual product titles, descriptions, images, seller-provided attributes, prices, specifications, marketplace metadata, and other externally acquired information.

An Observation therefore answers the question:

"What was directly observed?"

Evidence

Evidence represents interpreted information extracted from one or more observations. Unlike observations, evidence is produced through analysis and therefore carries an associated level of confidence or reliability.

Evidence may support multiple competing interpretations simultaneously and should never be regarded as proof of a particular conclusion. Instead, it provides measurable support for subsequent reasoning.

Evidence therefore answers the question:

"What does the available information suggest?"

Claim

A Claim represents a structured statement that may be supported by one or more pieces of evidence.

Claims express explicit propositions regarding a product, such as the presence of a particular feature, compatibility with another product, product category membership, manufacturer identity, or model designation.

Multiple claims may coexist, including mutually competing claims, provided each maintains explicit links to its supporting evidence.

A Claim therefore answers the question:

"What can reasonably be asserted?"

Product Hypothesis

A Product Hypothesis represents a complete candidate interpretation of the product being analysed.

Rather than evaluating individual characteristics in isolation, the hypothesis combines multiple claims into a coherent explanation of the available evidence. Multiple competing hypotheses may exist simultaneously until sufficient evidence allows one interpretation to be preferred over the others.

Product hypotheses therefore represent the principal reasoning objects of the Product Understanding Engine.

A Product Hypothesis answers the question:

"What product does the available evidence collectively describe?"

Candidate

A Candidate represents a potential match retrieved from one or more knowledge sources for evaluation against the current product hypothesis.

Candidates originate from external product catalogues, manufacturer databases, marketplace inventories, or other structured knowledge repositories. Their purpose is not to determine the correct product but to provide possible explanations that may be evaluated by the reasoning process.

Multiple candidates may remain under consideration until sufficient evidence permits elimination or selection.

A Candidate therefore answers the question:

"Which known products could plausibly correspond to this hypothesis?"

Decision

A Decision represents the final outcome produced by the Product Understanding Engine.

Unlike intermediate reasoning objects, a decision constitutes an actionable conclusion. It identifies the selected product interpretation together with the supporting rationale, its uncertainty profile, any calibrated Decision confidence, and remaining uncertainty relevant to downstream systems.

Importantly, a Decision does not replace the reasoning process that produced it. Instead, it serves as a traceable endpoint whose supporting observations, evidence, claims, and hypotheses remain available for inspection and explanation.

A Decision therefore answers the question:

"What conclusion should the system act upon?"

## A.4 Reference Information Flow

The Product Understanding Engine performs product understanding through a progressive sequence of information refinement. Each architectural object contributes to the reasoning process by transforming information into increasingly structured and reliable representations. No architectural stage bypasses this sequence, thereby ensuring that every decision remains traceable to its originating observations.

The reference information flow is illustrated conceptually as follows:

Observation → Evidence → Claim → Product Hypothesis → Candidate Evaluation → Decision → Learning

Although individual implementations may execute multiple stages concurrently or iteratively, the logical ordering of these transformations remains unchanged.

Observation Acquisition

The reasoning process begins with the acquisition of one or more observations from external sources. These observations are recorded without interpretation and collectively represent the complete set of information available to the system at the time of analysis.

Observations remain immutable throughout the reasoning process, providing a permanent record of the information upon which subsequent conclusions are based.

Evidence Construction

The acquired observations are analysed to produce evidence. During this stage, the system identifies potentially meaningful information while preserving explicit links to the observations from which the evidence was derived.

Multiple pieces of evidence may originate from a single observation, and individual evidence objects may combine information originating from several observations.

Claim Formation

Evidence is synthesised into explicit claims describing characteristics of the product under investigation.

Claims do not represent final conclusions. Instead, they express propositions supported by available evidence and remain subject to revision as additional evidence becomes available.

The architecture permits multiple competing claims to coexist simultaneously where the available evidence does not uniquely support a single interpretation.

Product Hypothesis Construction

Claims are combined into one or more complete product hypotheses.

Each hypothesis represents a coherent explanation of the available evidence and attempts to describe the complete identity of the product rather than isolated characteristics.

The architecture assumes that uncertainty exists naturally throughout this stage. Consequently, multiple hypotheses may remain active until further reasoning permits weaker alternatives to be rejected.

Candidate Evaluation

Product hypotheses are evaluated against candidate products retrieved from one or more knowledge sources.

Candidate evaluation determines the degree to which each known product explains the accumulated evidence while identifying inconsistencies, missing information, or conflicting characteristics.

The purpose of this stage is not merely to retrieve similar products but to determine which candidate most satisfactorily explains the observed evidence.

Decision Formation

Once sufficient evidence has accumulated, the reasoning process produces a decision.

The decision represents the preferred product interpretation together with its supporting rationale, remaining uncertainty, and any information necessary for downstream systems to understand or verify the conclusion.

Importantly, the decision does not discard alternative reasoning paths. Competing hypotheses and their supporting evidence remain available to support future explanation, auditing, or reconsideration.

Learning

Following completion of reasoning, the Decision and its associated history may create Feedback and Learning Records. Proposed improvements become Change Candidates, are evaluated offline, and enter future reasoning only through a Released Capability Version. Completed Decisions and their original reasoning remain unchanged.

## A.5 Architectural Relationships

The architectural objects defined within the Product Understanding Engine are connected through explicit dependency relationships. These relationships establish the flow of information while preserving provenance, explainability, and traceability throughout the reasoning process.

The following relationships define the reference architecture:

An Observation may contribute to zero, one, or many pieces of Evidence.
A piece of Evidence must reference one or more originating Observations.
A Claim may be supported by one or more pieces of Evidence.
Individual pieces of Evidence may support multiple independent Claims.
A Product Hypothesis consists of one or more related Claims that collectively describe a candidate interpretation.
A Candidate represents an external product against which one or more Product Hypotheses are evaluated.
A Decision references the selected Product Hypothesis together with the reasoning chain that justified its selection.
The Learning subsystem may reference any architectural object when creating Learning Records and Change Candidates, but it must not modify completed reasoning or live capabilities directly.

These relationships ensure that every decision produced by the Product Understanding Engine remains fully traceable from its final conclusion to the original observations upon which the reasoning process was based.

## A.6 Module Contracts

The Product Understanding Engine is organised as a collection of independent architectural modules. Each module is responsible for a specific stage of the reasoning process and communicates with neighbouring modules through well-defined architectural contracts.

These contracts define the responsibilities of each module together with the architectural objects they consume and produce. They intentionally avoid prescribing implementation technologies, allowing individual implementations to employ alternative algorithms while preserving architectural consistency.

### Observation Acquisition Module

**Purpose**

Acquire product information from one or more external sources and convert it into Observation objects.

**Consumes**

External product information.
Marketplace listings.
Images.
Product metadata.
Structured or unstructured information.

**Produces**

Observation objects.

**Responsibilities**

Acquire information without interpretation.
Preserve provenance.
Record observations in immutable form.
Capture all available information relevant to the current product.

### Evidence Construction Module

**Purpose**

Transform observations into structured evidence suitable for reasoning.

**Consumes**

Observation objects.

**Produces**

Evidence objects.

**Responsibilities**

Analyse observations.
Extract meaningful information.
Record the relevant extraction confidence, reliability, and limitations where appropriate.
Preserve links to originating observations.
Support multiple independent pieces of evidence from a single observation.

### Claim Generation Module

**Purpose**

Convert evidence into explicit factual propositions describing characteristics of the product.

**Consumes**

Evidence objects.

**Produces**

Claim objects.

**Responsibilities**

Form explicit assertions.
Maintain traceability to supporting evidence.
Permit competing claims where uncertainty exists.
Avoid premature elimination of alternative interpretations.

### Hypothesis Construction Module

**Purpose**

Combine related claims into coherent explanations representing possible product identities.

**Consumes**

Claim objects.

**Produces**

Product Hypothesis objects.

**Responsibilities**

Construct complete product interpretations.
Maintain multiple competing hypotheses.
Integrate supporting and conflicting evidence.
Represent uncertainty explicitly.

### Candidate Retrieval Module

**Purpose**

Retrieve known products capable of explaining the current hypotheses.

**Consumes**

Product Hypothesis objects.

**Produces**

Candidate objects.

**Responsibilities**

Search one or more knowledge repositories.
Retrieve plausible candidate products.
Avoid premature exclusion of potentially valid candidates.
Support multiple knowledge sources.

### Candidate Evaluation Module

**Purpose**

Determine how well each candidate explains the available evidence.

**Consumes**

Candidate objects.
Product Hypothesis objects.
Supporting claims and evidence.

**Produces**

Ranked candidate evaluations.

**Responsibilities**

Compare candidates against hypotheses.
Identify agreements and conflicts.
Assess completeness.
Preserve explainability throughout the evaluation process.

### Decision Module

**Purpose**

Produce the final architectural output of the Product Understanding Engine.

**Consumes**

Candidate evaluations.

**Produces**

Decision objects.

**Responsibilities**

Select the preferred interpretation.
Preserve supporting reasoning.
Record remaining uncertainty.
Produce outputs suitable for downstream systems.

### Learning Module

**Purpose**

Improve future reasoning using historical observations and completed decisions.

**Consumes**

Decisions.
Observations.
Evidence.
Claims.
Product Hypotheses.

**Produces**

Learning Records, Change Candidates, Evaluation Results, and approved Released Capability Versions.

**Responsibilities**

Identify recurring failures and improvement opportunities.
Create versioned Change Candidates.
Evaluate proposed changes against representative and regression datasets.
Release only approved capability or knowledge versions.
Preserve reproducibility of completed Decisions and support rollback.

## A.7 Architectural Constraints

Every implementation of the Product Understanding Engine must satisfy the following architectural constraints regardless of the implementation technologies employed.

Observations must remain immutable once created.
Every Evidence object must reference its originating Observation or Observations.
Every Claim must be supported by identifiable Evidence.
Multiple competing Claims and Product Hypotheses must be permitted until sufficient evidence supports their elimination.
Every Decision must remain traceable to the complete reasoning chain from which it was derived.
Learning must not modify historical reasoning or alter live capabilities without evaluation and release approval.
Architectural modules must communicate exclusively through the defined architectural objects rather than implementation-specific internal representations.
The replacement of algorithms, machine learning models, databases, or software frameworks must not require modification of the architectural contracts defined within this appendix.

These constraints ensure that the Product Understanding Engine remains explainable, extensible, technology independent, and capable of supporting multiple implementation strategies while preserving architectural consistency.

## A.8 Extensibility

The Product Understanding Engine has been designed to accommodate future advances in artificial intelligence, information retrieval, knowledge representation, and reasoning without requiring modification of its fundamental architecture.

Architectural modules communicate exclusively through the core objects defined within this appendix. Consequently, individual modules may be replaced, refined, or extended provided they continue to satisfy the architectural contracts associated with their inputs and outputs. Improvements to one module therefore do not necessitate changes elsewhere within the system.

For example, Observation Acquisition may incorporate additional information sources, alternative sensing modalities, or improved data extraction techniques without affecting downstream reasoning. Similarly, Evidence Construction may employ symbolic methods, probabilistic reasoning, machine learning models, or future artificial intelligence techniques while continuing to produce architecturally equivalent Evidence objects.

The same principle applies throughout the remainder of the architecture. Candidate Retrieval may utilise alternative search technologies or knowledge representations, Candidate Evaluation may adopt more sophisticated comparison strategies, and Learning may incorporate future continual learning techniques without altering the overall reasoning pipeline.

This separation between architectural responsibilities and implementation technologies enables the Product Understanding Engine to evolve alongside advances in artificial intelligence while preserving the conceptual integrity of the architecture. As new algorithms, models, and computational techniques emerge, they may be incorporated into individual modules without requiring redesign of the overall system.

Accordingly, the reference architecture should be regarded as a stable architectural foundation rather than a fixed implementation. Its purpose is to define the enduring structural organisation of product understanding while allowing future implementations to adopt the most appropriate technologies available at the time of deployment.
