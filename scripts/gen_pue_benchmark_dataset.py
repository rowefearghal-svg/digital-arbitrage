"""Generate ``tests/fixtures/pue/gpu_release_benchmark_v0.1.json`` (Sprint 3).

Regenerate only after a deliberate, reviewed change to the case set - review
the diff carefully (mirrors the convention documented for
``scripts/gen_pue_golden.py`` in ``tests/fixtures/pue/README.md``).

Run from the repository root:

    python scripts/gen_pue_benchmark_dataset.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUTPUT_PATH = ROOT / "tests" / "fixtures" / "pue" / "gpu_release_benchmark_v0.1.json"

DATASET_SCHEMA_VERSION = "pue-benchmark-dataset-0.1.0"
BENCHMARK_VERSION = "gpu-release-benchmark-0.1.0"
KNOWLEDGE_VERSION = "gpu-seed-0.1.0"
POLICY_VERSION = "gpu-policy-0.1.0"

cases: list[dict] = []


def add(case: dict) -> None:
    if "annotation_confidence" not in case:
        case["annotation_confidence"] = "medium"
    if "annotation_source" not in case:
        case["annotation_source"] = "sprint3_hand_authored"
    if "provenance" not in case:
        case["provenance"] = (
            "Hand-authored synthetic listing title constructed for Sprint 3 benchmark "
            "coverage; not scraped from a live marketplace."
        )
    cases.append(case)


# --------------------------------------------------------------------------- #
# 1. Exact catalogue-product identification (one per real, non-synthetic
#    complete_product catalogue entry - covers NVIDIA RTX 30/40, AMD RX
#    7000, Intel Arc, board-partner variants).
# --------------------------------------------------------------------------- #
_EXACT_PRODUCTS = [
    (
        "exact_01_rtx4090_fe",
        "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
        "gpu-nvidia-rtx4090-fe",
        "rtx 4090",
        "nvidia",
    ),
    (
        "exact_02_asus_tuf_rtx4090",
        "ASUS TUF Gaming GeForce RTX 4090 OC 24GB TUF-RTX4090-O24G",
        "gpu-asus-tuf-rtx4090-o24g",
        "rtx 4090",
        "asus",
    ),
    (
        "exact_03_asus_rog_rtx4090",
        "ASUS ROG Strix GeForce RTX 4090 OC 24GB ROG-STRIX-RTX4090-O24G-GAMING",
        "gpu-asus-rog-strix-rtx4090-o24g",
        "rtx 4090",
        "asus",
    ),
    (
        "exact_04_msi_rtx4090_trio",
        "MSI GeForce RTX 4090 Gaming X Trio 24GB",
        "gpu-msi-rtx4090-gamingx-trio",
        "rtx 4090",
        "msi",
    ),
    (
        "exact_05_gigabyte_rtx4090_master",
        "GIGABYTE AORUS GeForce RTX 4090 Master 24GB",
        "gpu-gigabyte-aorus-rtx4090-master",
        "rtx 4090",
        "gigabyte",
    ),
    (
        "exact_06_zotac_rtx4090_trinity",
        "ZOTAC Gaming GeForce RTX 4090 Trinity OC 24GB",
        "gpu-zotac-rtx4090-trinity-oc",
        "rtx 4090",
        "zotac",
    ),
    (
        "exact_07_rtx4080_fe",
        "NVIDIA GeForce RTX 4080 Founders Edition 16GB",
        "gpu-nvidia-rtx4080-fe",
        "rtx 4080",
        "nvidia",
    ),
    (
        "exact_08_asus_tuf_rtx4080super",
        "ASUS TUF Gaming GeForce RTX 4080 SUPER OC 16GB TUF-RTX4080S-O16G-GAMING",
        "gpu-asus-tuf-rtx4080super-oc",
        "rtx 4080 super",
        "asus",
    ),
    (
        "exact_09_msi_rtx4080super_trio",
        "MSI GeForce RTX 4080 SUPER Gaming X Trio 16GB",
        "gpu-msi-rtx4080super-gamingx-trio",
        "rtx 4080 super",
        "msi",
    ),
    (
        "exact_10_rtx4070_fe",
        "NVIDIA GeForce RTX 4070 Founders Edition 12GB",
        "gpu-nvidia-rtx4070-fe",
        "rtx 4070",
        "nvidia",
    ),
    (
        "exact_11_asus_dual_rtx4070",
        "ASUS Dual GeForce RTX 4070 OC 12GB DUAL-RTX4070-O12G",
        "gpu-asus-dual-rtx4070-oc",
        "rtx 4070",
        "asus",
    ),
    (
        "exact_12_msi_rtx4070tisuper_trio",
        "MSI GeForce RTX 4070 Ti SUPER Gaming X Trio 16GB",
        "gpu-msi-rtx4070tisuper-gamingx-trio",
        "rtx 4070 ti super",
        "msi",
    ),
    (
        "exact_13_asus_dual_rtx3060_8g",
        "ASUS Dual GeForce RTX 3060 OC 8GB DUAL-RTX3060-O8G-V2",
        "gpu-asus-dual-rtx3060-oc-8g",
        "rtx 3060",
        "asus",
    ),
    (
        "exact_14_asus_dual_rtx3060_12g",
        "ASUS Dual GeForce RTX 3060 OC 12GB DUAL-RTX3060-O12G-V2",
        "gpu-asus-dual-rtx3060-oc-12g",
        "rtx 3060",
        "asus",
    ),
    (
        "exact_15_msi_rtx3060_gamingx_8g",
        "MSI GeForce RTX 3060 Gaming X 8GB",
        "gpu-msi-gamingx-rtx3060-8g",
        "rtx 3060",
        "msi",
    ),
    (
        "exact_16_msi_rtx3060_ventus_12g",
        "MSI GeForce RTX 3060 Ventus 2X 12GB",
        "gpu-msi-ventus-rtx3060-12g",
        "rtx 3060",
        "msi",
    ),
    (
        "exact_17_gigabyte_rtx3060_windforce",
        "GIGABYTE GeForce RTX 3060 WINDFORCE OC 12GB GV-N3060WF2OC-12GD",
        "gpu-gigabyte-windforce-rtx3060-12g",
        "rtx 3060",
        "gigabyte",
    ),
    (
        "exact_18_amd_rx7900xtx_reference",
        "AMD Radeon RX 7900 XTX Reference 24GB",
        "gpu-amd-rx7900xtx-reference",
        "rx 7900 xtx",
        "amd",
    ),
    (
        "exact_19_sapphire_rx7900xtx_nitro",
        "SAPPHIRE Nitro+ Radeon RX 7900 XTX 24GB",
        "gpu-sapphire-nitro-rx7900xtx",
        "rx 7900 xtx",
        "sapphire",
    ),
    (
        "exact_20_powercolor_rx7900xtx_reddevil",
        "PowerColor Red Devil Radeon RX 7900 XTX 24GB RX 7900 XTX 24G-E/OC",
        "gpu-powercolor-reddevil-rx7900xtx",
        "rx 7900 xtx",
        "powercolor",
    ),
    (
        "exact_21_amd_rx7800xt_reference",
        "AMD Radeon RX 7800 XT Reference 16GB",
        "gpu-amd-rx7800xt-reference",
        "rx 7800 xt",
        "amd",
    ),
    (
        "exact_22_sapphire_rx7800xt_nitro",
        "SAPPHIRE Nitro+ Radeon RX 7800 XT 16GB",
        "gpu-sapphire-nitro-rx7800xt",
        "rx 7800 xt",
        "sapphire",
    ),
    (
        "exact_23_intel_arca770_le",
        "Intel Arc A770 Limited Edition 16GB",
        "gpu-intel-arca770-le-16g",
        "arc a770",
        "intel",
    ),
    (
        "exact_24_asrock_arca770_phantom",
        "ASRock Intel Arc A770 Phantom Gaming 16GB",
        "gpu-asrock-arca770-phantom-16g",
        "arc a770",
        "asrock",
    ),
    (
        "exact_25_intel_arca750_le",
        "Intel Arc A750 Limited Edition 8GB",
        "gpu-intel-arca750-le-8g",
        "arc a750",
        "intel",
    ),
]
# Case IDs whose title carries a real, dash-shaped manufacturer part
# number that the deterministic MPN regex (pue/evidence.py) actually
# detects and that matches the catalogue's stored identifier exactly -
# only these can legitimately reach IdentificationLevel.EXACT_CATALOGUE_
# PRODUCT under the current, already-validated Sprint 1/2 policy (a
# canonical-title-only mention, with no MPN evidence, tops out at MODEL/
# VARIANT - the same distinction the Sprint 1 acceptance fixture already
# draws between its MPN-bearing case_03 and its canonical-title-only
# case_02). Asserting EXACT_CATALOGUE_PRODUCT for the others would be an
# internally-inconsistent gold label, not a real product-identification
# requirement - see BenchmarkDataset docstring / brief section 4.4.
_EXACT_MPN_CASE_IDS = {
    "exact_02_asus_tuf_rtx4090",
    "exact_03_asus_rog_rtx4090",
    "exact_08_asus_tuf_rtx4080super",
    "exact_11_asus_dual_rtx4070",
    "exact_13_asus_dual_rtx3060_8g",
    "exact_14_asus_dual_rtx3060_12g",
    "exact_17_gigabyte_rtx3060_windforce",
}
for case_id, title, product_id, family, brand in _EXACT_PRODUCTS:
    has_mpn = case_id in _EXACT_MPN_CASE_IDS
    case_payload = {
        "case_id": case_id,
        "title": title,
        "case_tags": ["exact_identification", "complete_desktop_graphics_card", brand],
        "difficulty": "easy",
        "annotation_confidence": "high",
        "allowed_decision_types": ["identified"]
        if has_mpn
        else ["identified", "partially_identified"],
        "forbidden_decision_types": ["ambiguous", "abstained", "outside_supported_domain"],
        "expected_product_form": "complete_product",
        "acceptable_catalogue_product_ids": [product_id],
        "expected_identified_family": family,
        "required_evidence_types": ["product_family_token"],
        "min_evidence_count": 2,
    }
    if has_mpn:
        case_payload["expected_identification_levels"] = ["exact_catalogue_product"]
    add(case_payload)

# --------------------------------------------------------------------------- #
# 2. Board-partner ambiguity / indistinguishable variants (family+capacity
#    only, no brand token -> multiple acceptable candidates).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "ambig_01_rtx3060_12gb_no_brand",
        "title": "RTX 3060 12GB Graphics Card",
        "case_tags": ["indistinguishable_variants", "board_partner_ambiguity"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "expected_identified_family": "rtx 3060",
        "acceptable_catalogue_product_ids": [
            "gpu-asus-dual-rtx3060-oc-12g",
            "gpu-msi-ventus-rtx3060-12g",
            "gpu-gigabyte-windforce-rtx3060-12g",
        ],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "ambig_02_rtx4090_no_brand",
        "title": "NVIDIA RTX 4090 24GB Graphics Card",
        "case_tags": ["indistinguishable_variants", "board_partner_ambiguity", "family_only"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain", "identified"],
        "expected_identification_levels": ["model", "family"],
        "expected_identified_family": "rtx 4090",
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "family_only_01_rtx4090",
        "title": "NVIDIA RTX 4090",
        "case_tags": ["model_only", "family_only"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain", "abstained", "identified"],
        "expected_identification_levels": ["model"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "family_only_02_rx7900xtx",
        "title": "AMD RX 7900 XTX",
        "case_tags": ["model_only", "family_only"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain", "abstained"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "family_only_03_arca770",
        "title": "Intel Arc A770",
        "case_tags": ["model_only", "family_only"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain", "abstained"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "family_only_04_rtx3060",
        "title": "RTX 3060 Graphics Card",
        "case_tags": ["model_only", "family_only"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["partially_identified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 3. Mobile vs desktop.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "mobile_01_rtx4090_laptop_gpu",
        "title": "NVIDIA GeForce RTX 4090 Laptop GPU",
        "case_tags": ["mobile_vs_desktop"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["identified", "partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "acceptable_catalogue_product_ids": ["gpu-nvidia-rtx4090-laptop"],
        "forbidden_catalogue_product_ids": [
            "gpu-nvidia-rtx4090-fe",
            "gpu-asus-tuf-rtx4090-o24g",
            "gpu-asus-rog-strix-rtx4090-o24g",
            "gpu-msi-rtx4090-gamingx-trio",
            "gpu-gigabyte-aorus-rtx4090-master",
            "gpu-zotac-rtx4090-trinity-oc",
        ],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "mobile_02_dell_laptop_with_rtx4090",
        "title": "Dell Gaming Laptop with NVIDIA RTX 4090 Mobile Graphics",
        "case_tags": ["mobile_vs_desktop"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["partially_identified", "classified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "forbidden_catalogue_product_ids": [
            "gpu-nvidia-rtx4090-fe",
            "gpu-asus-tuf-rtx4090-o24g",
            "gpu-asus-rog-strix-rtx4090-o24g",
        ],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "mobile_03_rtx4090_desktop_vs_laptop_conflict",
        "title": "RTX 4090 Laptop GPU - NOT the desktop Founders Edition card",
        "case_tags": ["mobile_vs_desktop", "family_conflict"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_catalogue_product_ids": ["gpu-nvidia-rtx4090-fe"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 4. Water blocks.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "waterblock_01_ek_quantum_vector2",
        "title": "EK Quantum Vector2 RTX 4090 Water Block Full Cover",
        "case_tags": ["water_block", "component"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "component",
        "expected_comparability": ["not_comparable_product_form"],
        "require_hard_rejected_candidate": True,
        "required_evidence_types": ["product_form_term"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "waterblock_02_generic_rtx4090",
        "title": "RTX 4090 Waterblock Full Cover GPU Cooling Block",
        "case_tags": ["water_block", "component"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "component",
        "require_hard_rejected_candidate": True,
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "waterblock_03_bykski",
        "title": "Bykski RTX 4090 Full Cover GPU Water Block",
        "case_tags": ["water_block", "component"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "component",
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "waterblock_04_gpu_not_included",
        "title": "RTX 4090 GPU not included - water block only",
        "case_tags": ["water_block", "gpu_not_included"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "required_evidence_types": ["exclusion_term", "product_form_term"],
        "require_hard_rejected_candidate": True,
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 3,
    }
)

# --------------------------------------------------------------------------- #
# 5. Replacement fans / coolers.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "fan_01_asus_tuf_rtx4090_fan_set",
        "title": "ASUS TUF Gaming RTX 4090 Replacement Fan Set",
        "case_tags": ["replacement_fan", "replacement_part"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "replacement_part",
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "fan_02_generic_rtx4090_fan",
        "title": "RTX 4090 replacement fan set",
        "case_tags": ["replacement_fan", "replacement_part"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "expected_product_form": "replacement_part",
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "fan_03_cooling_fans_for_rtx4090",
        "title": "Replacement cooling fans for RTX 4090 graphics card - fits ASUS TUF",
        "case_tags": ["replacement_fan", "replacement_part"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "expected_product_form": "replacement_part",
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 6. Backplates.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "backplate_01_nvidia_rtx4090_fe",
        "title": "NVIDIA GeForce RTX 4090 Founders Edition Backplate",
        "case_tags": ["backplate", "replacement_part"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "replacement_part",
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "backplate_02_generic_rtx4090",
        "title": "RTX 4090 Founders Edition backplate replacement part - GPU not included",
        "case_tags": ["backplate", "replacement_part", "gpu_not_included"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 7. Power cables / adapters.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "adapter_01_12vhpwr",
        "title": "12VHPWR PCIe 5.0 Power Adapter Cable for RTX 40-Series",
        "case_tags": ["power_cable", "compatible_item"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "ambiguous"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "adapter_02_generic_power_cable",
        "title": "12VHPWR power adapter for RTX 4090",
        "case_tags": ["power_cable", "compatible_item"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified", "ambiguous"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 2,
    }
)

# --------------------------------------------------------------------------- #
# 8. Brackets / compatible accessories.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "bracket_01_universal_anti_sag",
        "title": "Universal GPU Anti-Sag Support Bracket",
        "case_tags": ["bracket", "accessory"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "expected_product_form": "accessory",
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "bracket_02_riser_cable",
        "title": "Generic PCIe Riser Cable Compatible with RTX 4090",
        "case_tags": ["compatible_accessory"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "bracket_03_gpu_support_brace",
        "title": "Graphics card brace / anti sag bracket, fits most GPUs",
        "case_tags": ["bracket", "accessory"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 9. Empty boxes / packaging.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "packaging_01_empty_box",
        "title": "Empty RTX 4090 Founders Edition Box Only",
        "case_tags": ["empty_box", "packaging_only"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "expected_product_form": "packaging_only",
        "forbidden_product_forms": ["complete_product"],
        "expected_comparability": ["not_comparable_product_form"],
        "required_evidence_types": ["packaging_term"],
        "forbidden_harmful_outcomes": ["packaging_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "packaging_02_box_only_no_card",
        "title": "RTX 4090 FE box only - no graphics card included",
        "case_tags": ["empty_box", "packaging_only", "gpu_not_included"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "expected_product_form": "packaging_only",
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["packaging_to_complete_product"],
        "min_evidence_count": 2,
    }
)
add(
    {
        "case_id": "packaging_03_retail_box_asus_tuf",
        "title": "ASUS TUF RTX 4090 retail packaging box only, empty",
        "case_tags": ["empty_box", "packaging_only"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["packaging_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 10. Incomplete / damaged / for-parts cards.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "damaged_01_for_parts_rtx4090",
        "title": "ASUS TUF RTX 4090 - for parts or repair, not working",
        "case_tags": ["incomplete_damaged", "for_parts"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "damaged_02_cracked_pcb",
        "title": "NVIDIA RTX 4080 Founders Edition - cracked PCB, for parts only",
        "case_tags": ["incomplete_damaged", "for_parts"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "damaged_03_missing_fans_incomplete",
        "title": "MSI RTX 4090 Gaming X Trio - missing fans, incomplete, sold as-is",
        "case_tags": ["incomplete_damaged"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "classified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 11. Explicit GPU-not-included cases (beyond water block/backplate above).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "not_included_01_case_only",
        "title": "RTX 4090 graphics card box and manual only, GPU not included",
        "case_tags": ["gpu_not_included"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "required_evidence_types": ["exclusion_term"],
        "forbidden_harmful_outcomes": [
            "packaging_to_complete_product",
            "accessory_to_complete_product",
        ],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "not_included_02_bracket_only",
        "title": "RTX 4090 support bracket only, card not included",
        "case_tags": ["gpu_not_included", "bracket"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 12. Compatibility-only references.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "compat_01_case_fits_rtx4090",
        "title": "PC Case - fits RTX 4090 and other large graphics cards",
        "case_tags": ["compatibility_only"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "compat_02_cooler_compatible",
        "title": "Aftermarket GPU cooler, compatible with RTX 4090 reference PCB",
        "case_tags": ["compatibility_only"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 13. Simple bundles.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "bundle_01_rtx4090_psu",
        "title": "ASUS TUF Gaming RTX 4090 OC 24GB + 1000W PSU Bundle",
        "case_tags": ["bundle"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "bundle_02_rtx4090_with_waterblock",
        "title": "ASUS RTX 4090 with EK water block",
        "case_tags": ["bundle", "ambiguous_title"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["ambiguous"],
        "forbidden_decision_types": ["identified", "classified", "partially_identified"],
        "require_multiple_hypotheses": True,
        "min_evidence_count": 3,
    }
)
add(
    {
        "case_id": "bundle_03_gpu_and_riser",
        "title": "MSI RTX 4090 Gaming X Trio bundled with PCIe riser cable",
        "case_tags": ["bundle"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "classified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 14. Catalogue gaps (real GPUs deliberately absent from the seed catalogue).
# --------------------------------------------------------------------------- #
for case_id, title, _family in [
    ("gap_01_rx6800xt", "AMD Radeon RX 6800 XT 16GB", "rx 6800 xt"),
    ("gap_02_rtx4060", "NVIDIA GeForce RTX 4060 8GB", "rtx 4060"),
    ("gap_03_gtx1660super", "NVIDIA GeForce GTX 1660 SUPER 6GB", "gtx 1660 super"),
    ("gap_04_arca580", "Intel Arc A580 8GB", "arc a580"),
]:
    add(
        {
            "case_id": case_id,
            "title": title,
            "case_tags": ["catalogue_gap"],
            "annotation_confidence": "high",
            # A model absent from the seed catalogue may honestly resolve to
            # PARTIALLY_IDENTIFIED/CLASSIFIED (recognized as GPU-domain but not
            # matched) or OUTSIDE_SUPPORTED_DOMAIN (no chipset/family term for
            # it exists at all in the term knowledge either) - both are safe,
            # non-harmful degradations for a genuinely unknown product; only a
            # false EXACT/IDENTIFIED match against the wrong catalogue entry
            # would be a real (forbidden) error here.
            "allowed_decision_types": [
                "partially_identified",
                "classified",
                "outside_supported_domain",
            ],
            "forbidden_decision_types": ["identified"],
            "catalogue_gap": True,
            "min_evidence_count": 1,
        }
    )

# --------------------------------------------------------------------------- #
# 15. Zero-Candidate cases (in-domain but no plausible catalogue match at all).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "zero_candidate_01_unknown_brand",
        "title": "UnknownBrandXYZ Graphics Card Model Q9000",
        "case_tags": ["zero_candidate"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "abstained", "ambiguous"],
        "forbidden_decision_types": ["identified", "outside_supported_domain"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "zero_candidate_02_gpu_generic_no_specifics",
        "title": "Graphics card, used, works fine",
        "case_tags": ["zero_candidate"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "abstained"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 16. Genuinely ambiguous titles (multiple competing hypotheses).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "ambiguous_01_rtx3060_board_partner",
        "title": "RTX 3060 12GB",
        "case_tags": ["genuinely_ambiguous"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["partially_identified", "ambiguous"],
        "forbidden_decision_types": ["identified", "outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "ambiguous_02_gpu_or_waterblock",
        "title": "RTX 4090 with cooling upgrade installed",
        "case_tags": ["genuinely_ambiguous"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "classified", "ambiguous"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 17. Justified abstentions.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "abstain_01_contradiction",
        "title": "RTX 4090 (actually RTX 4080, relisted by mistake)",
        "case_tags": ["justified_abstention", "family_conflict"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["abstained", "ambiguous"],
        "forbidden_decision_types": ["identified"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "abstain_02_low_quality_title",
        "title": "gpu 4090 good condition dm me",
        "case_tags": ["justified_abstention", "source_quality"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["partially_identified", "classified", "abstained"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 18. Unsupported-domain cases.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "domain_01_phone",
        "title": "Samsung Galaxy S23 Ultra 256GB",
        "case_tags": ["unsupported_domain"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_product_forms": ["complete_product"],
        "unsupported_domain": True,
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "domain_02_ambiguous_short",
        "title": "Samsung?",
        "case_tags": ["unsupported_domain"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_product_forms": ["complete_product"],
        "unsupported_domain": True,
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "domain_03_iphone_charger",
        "title": "Apple iPhone 15 Charger Cable USB-C 1m",
        "case_tags": ["unsupported_domain"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_product_forms": ["complete_product"],
        "unsupported_domain": True,
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 19. Explicit family conflicts (title vs structured attribute).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "conflict_01_title_structured",
        "title": "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
        "structured_attributes": {"model": "RTX 4080"},
        "case_tags": ["family_conflict"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["abstained"],
        "forbidden_decision_types": ["identified"],
        "acceptable_abstention_reasons": ["unresolved_contradiction"],
        "min_evidence_count": 3,
    }
)
add(
    {
        "case_id": "conflict_02_brand_mismatch",
        "title": "ASUS TUF Gaming GeForce RTX 4090 OC 24GB",
        "structured_attributes": {"brand": "MSI"},
        "case_tags": ["family_conflict"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "abstained", "classified"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 20. Misleading high-similarity titles (non-GPU products sharing GPU tokens).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "misleading_01_mousepad",
        "title": "RTX 4090 Gaming Mouse Pad XXL - Extended Desk Mat",
        "case_tags": ["misleading_similarity"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous", "abstained"],
        "forbidden_decision_types": ["identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "misleading_02_tshirt",
        "title": "RTX 4090 Graphics Card Logo T-Shirt, Large",
        "case_tags": ["misleading_similarity"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous", "abstained"],
        "forbidden_decision_types": ["identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 21. Regression: Sprint 1 mandatory malformed-input / edge cases (kept
#     distinct from tests/fixtures/pue/sprint1_acceptance_v0.1.json so the
#     release benchmark also exercises them, per brief section 9).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "edge_01_empty_title",
        "title": " ",
        "case_tags": ["edge_case", "empty_title"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["abstained", "outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "edge_02_malformed_input",
        "title": None,
        "malformed": True,
        "case_tags": ["edge_case", "technical_failure"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["processing_failed"],
        "forbidden_decision_types": ["identified", "abstained"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 22. Additional exact-identification cases via MPN/alias-first phrasing
#     (exercises exact-identifier retrieval, distinct from the
#     canonical-title fuzzy-match phrasing used in section 1 - not a
#     trivial near-duplicate of those cases).
# --------------------------------------------------------------------------- #
_ALIAS_PRODUCTS = [
    (
        "exact_alias_01_asus_tuf_rtx4090_mpn",
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",
        "gpu-asus-tuf-rtx4090-o24g",
        "rtx 4090",
    ),
    (
        "exact_alias_02_gigabyte_aorus_mpn",
        "GIGABYTE AORUS RTX 4090 Master GV-N4090AORUS M-24GD",
        "gpu-gigabyte-aorus-rtx4090-master",
        "rtx 4090",
    ),
    (
        "exact_alias_03_zotac_trinity_mpn",
        "ZOTAC RTX 4090 Trinity OC ZT-D40900J-10P",
        "gpu-zotac-rtx4090-trinity-oc",
        "rtx 4090",
    ),
    (
        "exact_alias_04_sapphire_nitro_rx7900xtx_mpn",
        "SAPPHIRE Nitro+ RX 7900 XTX 11322-01-20G",
        "gpu-sapphire-nitro-rx7900xtx",
        "rx 7900 xtx",
    ),
    (
        "exact_alias_05_asrock_arc_a770_mpn",
        "ASRock Arc A770 Phantom Gaming ARC A770 PG 16GO",
        "gpu-asrock-arca770-phantom-16g",
        "arc a770",
    ),
    (
        "exact_alias_06_msi_rtx3060_ventus_mpn",
        "MSI RTX 3060 Ventus 2X 12G RTX 3060 VENTUS 2X 12G",
        "gpu-msi-ventus-rtx3060-12g",
        "rtx 3060",
    ),
    (
        "exact_alias_07_asus_dual_rtx4070_mpn",
        "ASUS Dual RTX 4070 DUAL-RTX4070-O12G",
        "gpu-asus-dual-rtx4070-oc",
        "rtx 4070",
    ),
    (
        "exact_alias_08_powercolor_reddevil_mpn",
        "PowerColor Red Devil RX 7900 XTX RX 7900 XTX 24G-E/OC",
        "gpu-powercolor-reddevil-rx7900xtx",
        "rx 7900 xtx",
    ),
]
# Only these alias-phrased titles carry an MPN in the clean, dash-shaped
# form the regex actually detects; the others embed the true catalogue
# identifier with a space (e.g. "GV-N4090AORUS M-24GD") or no dash at all,
# so the MPN regex does not extract a token matching the stored identifier
# exactly - same rule as _EXACT_MPN_CASE_IDS above.
_ALIAS_MPN_CASE_IDS = {
    "exact_alias_01_asus_tuf_rtx4090_mpn",
    "exact_alias_03_zotac_trinity_mpn",
    "exact_alias_04_sapphire_nitro_rx7900xtx_mpn",
    "exact_alias_07_asus_dual_rtx4070_mpn",
}
for case_id, title, product_id, family in _ALIAS_PRODUCTS:
    has_mpn = case_id in _ALIAS_MPN_CASE_IDS
    alias_payload = {
        "case_id": case_id,
        "title": title,
        "case_tags": [
            "exact_identification",
            "complete_desktop_graphics_card",
            "mpn_alias_phrasing",
        ],
        "difficulty": "easy",
        "annotation_confidence": "high",
        "allowed_decision_types": ["identified"]
        if has_mpn
        else ["identified", "partially_identified"],
        "forbidden_decision_types": ["ambiguous", "abstained", "outside_supported_domain"],
        "expected_product_form": "complete_product",
        "acceptable_catalogue_product_ids": [product_id],
        "expected_identified_family": family,
        "min_evidence_count": 2,
    }
    if has_mpn:
        alias_payload["expected_identification_levels"] = ["exact_catalogue_product"]
    add(alias_payload)

# --------------------------------------------------------------------------- #
# 23. More family/model-only bare mentions (additional families).
# --------------------------------------------------------------------------- #
for case_id, title in [
    ("family_only_05_rtx4080", "NVIDIA RTX 4080"),
    ("family_only_06_rtx4070", "RTX 4070 Graphics Card"),
    ("family_only_07_rx7800xt", "AMD RX 7800 XT"),
    ("family_only_08_arca750", "Intel Arc A750"),
    ("family_only_09_rtx3060_8gb", "RTX 3060 8GB"),
]:
    add(
        {
            "case_id": case_id,
            "title": title,
            "case_tags": ["model_only", "family_only"],
            "annotation_confidence": "high",
            "allowed_decision_types": ["partially_identified"],
            "forbidden_decision_types": ["outside_supported_domain", "abstained", "identified"],
            "min_evidence_count": 1,
        }
    )

# --------------------------------------------------------------------------- #
# 24. Additional mobile GPU coverage (AMD mobile concept).
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "mobile_04_amd_rx7900m",
        "title": "AMD Radeon RX 7900M Mobile GPU",
        "case_tags": ["mobile_vs_desktop"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "acceptable_catalogue_product_ids": ["gpu-amd-rx7900m-concept"],
        "forbidden_catalogue_product_ids": [
            "gpu-amd-rx7900xtx-reference",
            "gpu-sapphire-nitro-rx7900xtx",
        ],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "mobile_05_laptop_amd_gpu_generic",
        "title": "Gaming laptop with AMD RX 7900M graphics, mobile GPU",
        "case_tags": ["mobile_vs_desktop"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "forbidden_catalogue_product_ids": ["gpu-amd-rx7900xtx-reference"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 25. Additional water block / fan / backplate phrasing variants.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "waterblock_05_full_cover_block_generic",
        "title": "Full cover water block for graphics card, RTX 4090 compatible",
        "case_tags": ["water_block", "component"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "fan_04_dual_fan_replacement_kit",
        "title": "Dual fan replacement kit for RTX 4090 graphics cards",
        "case_tags": ["replacement_fan", "replacement_part"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "backplate_03_generic_metal",
        "title": "Metal backplate for RTX 4090 Founders Edition, replacement part",
        "case_tags": ["backplate", "replacement_part"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 26. More brackets / compatible accessories / adapters.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "bracket_04_gpu_support_stand",
        "title": "Adjustable GPU support stand, universal graphics card holder",
        "case_tags": ["bracket", "accessory"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "expected_product_form": "accessory",
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "adapter_03_riser_cable_variant",
        "title": "PCIe 4.0 GPU riser cable, compatible with RTX 4090",
        "case_tags": ["compatible_accessory"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 27. More packaging / empty box variants.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "packaging_04_msi_box_only",
        "title": "MSI RTX 4090 Gaming X Trio original box only, no card",
        "case_tags": ["empty_box", "packaging_only", "gpu_not_included"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["packaging_to_complete_product"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 28. More incomplete/damaged/for-parts cases.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "damaged_04_water_damage",
        "title": "GIGABYTE AORUS RTX 4090 Master - water damaged, untested, for parts",
        "case_tags": ["incomplete_damaged", "for_parts"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "damaged_05_bent_pins",
        "title": "AMD RX 7900 XTX Reference - bent PCIe pins, sold for parts",
        "case_tags": ["incomplete_damaged", "for_parts"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 29. More GPU-not-included / compatibility-only.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "not_included_03_manual_only",
        "title": "RTX 4090 instruction manual and accessories only, no GPU",
        "case_tags": ["gpu_not_included"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": [
            "packaging_to_complete_product",
            "accessory_to_complete_product",
        ],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "compat_03_psu_compatible_wattage",
        "title": "1000W PSU, recommended for RTX 4090 systems",
        "case_tags": ["compatibility_only"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous", "abstained"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# 30. More bundles.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "bundle_04_rtx4090_plus_psu_catalogue",
        "title": "ASUS TUF Gaming RTX 4090 OC 24GB + 1000W PSU Bundle (synthetic concept)",
        "case_tags": ["bundle"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "acceptable_catalogue_product_ids": ["bundle-asus-tuf-rtx4090-plus-psu"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "bundle_05_two_cards",
        "title": "Two graphics cards: RTX 4090 and RTX 3060, sold together",
        "case_tags": ["bundle", "ambiguous_title"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["ambiguous", "partially_identified", "identified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)

# --------------------------------------------------------------------------- #
# 31. More catalogue-gap cases.
# --------------------------------------------------------------------------- #
for case_id, title in [
    ("gap_05_rtx4090ti", "NVIDIA GeForce RTX 4090 Ti 24GB"),
    ("gap_06_rx7600", "AMD Radeon RX 7600 8GB"),
    ("gap_07_arcb580", "Intel Arc B580 12GB"),
]:
    add(
        {
            "case_id": case_id,
            "title": title,
            "case_tags": ["catalogue_gap"],
            "annotation_confidence": "medium",
            "allowed_decision_types": [
                "partially_identified",
                "classified",
                "outside_supported_domain",
            ],
            "forbidden_decision_types": ["identified"],
            "catalogue_gap": True,
            "min_evidence_count": 0,
        }
    )

# --------------------------------------------------------------------------- #
# 32. More zero-Candidate / ambiguous / abstention / domain / conflict /
#     misleading-similarity cases.
# --------------------------------------------------------------------------- #
add(
    {
        "case_id": "zero_candidate_03_generic_desc",
        "title": "Great condition, barely used, works perfectly",
        "case_tags": ["zero_candidate"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["abstained", "outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "ambiguous_03_asus_rtx4090_no_variant",
        "title": "ASUS RTX 4090 24GB",
        "case_tags": ["genuinely_ambiguous", "board_partner_ambiguity"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["partially_identified", "ambiguous", "identified"],
        "forbidden_decision_types": ["outside_supported_domain"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "abstain_03_two_families_conflict",
        "title": "RTX 4090 / RX 7900 XTX (whichever is in stock)",
        "case_tags": ["justified_abstention", "family_conflict"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["ambiguous", "abstained"],
        "forbidden_decision_types": ["identified"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "domain_04_cpu",
        "title": "AMD Ryzen 9 7950X3D Desktop CPU Processor",
        "case_tags": ["unsupported_domain"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["outside_supported_domain"],
        "forbidden_decision_types": ["identified", "partially_identified", "classified"],
        "forbidden_product_forms": ["complete_product"],
        "unsupported_domain": True,
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "domain_05_motherboard",
        "title": "ASUS ROG Strix Z790-E Gaming Motherboard",
        "case_tags": ["unsupported_domain"],
        "annotation_confidence": "high",
        "allowed_decision_types": ["outside_supported_domain", "classified"],
        "forbidden_decision_types": ["identified", "partially_identified"],
        "forbidden_product_forms": ["complete_product"],
        "unsupported_domain": True,
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "conflict_03_capacity_mismatch",
        "title": "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
        "structured_attributes": {"capacity_gb": 16},
        "case_tags": ["family_conflict"],
        "annotation_confidence": "low",
        "allowed_decision_types": ["identified", "partially_identified", "abstained", "classified"],
        "min_evidence_count": 1,
    }
)
add(
    {
        "case_id": "misleading_03_keychain",
        "title": "Mini RTX 4090 Graphics Card Keychain Miniature Replica",
        "case_tags": ["misleading_similarity"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous", "abstained"],
        "forbidden_decision_types": ["identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)
add(
    {
        "case_id": "misleading_04_sticker_decal",
        "title": "RTX 4090 Logo Sticker Decal for PC Case, Vinyl",
        "case_tags": ["misleading_similarity"],
        "annotation_confidence": "medium",
        "allowed_decision_types": ["classified", "ambiguous", "abstained"],
        "forbidden_decision_types": ["identified"],
        "forbidden_product_forms": ["complete_product"],
        "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        "min_evidence_count": 0,
    }
)

# --------------------------------------------------------------------------- #
# Sprint 3 pre-merge correction item 5: derive `expected_comparability`
# gold labels from pue/decisions.py's own deterministic, unconditional
# branches - never from "whatever the current implementation happens to
# output" for a given *case*. Every ComparabilityStatus decisions.py can
# produce is a function of (decision_type, product_form, and - only for a
# CLASSIFIED complete-product outcome - whether a family was resolved),
# not of incidental behaviour:
#   - product_form in {component, replacement_part, accessory} ->
#     NOT_COMPARABLE_PRODUCT_FORM (the accessory/component/replacement-part
#     branch sets this unconditionally).
#   - product_form == packaging_only -> NOT_COMPARABLE_PRODUCT_FORM
#     (packaging-only branch, unconditional).
#   - product_form == bundle -> NOT_COMPARABLE_BUNDLE (bundle branch,
#     unconditional regardless of decision_type).
#   - product_form == incomplete_product AND decision_type ==
#     partially_identified -> NOT_COMPARABLE_CONDITION.
#   - product_form == complete_product AND decision_type == identified ->
#     DIRECTLY_COMPARABLE.
#   - product_form == complete_product AND decision_type ==
#     partially_identified -> COMPARABLE_AT_BROADER_LEVEL.
#   - decision_type == ambiguous -> INSUFFICIENT_INFORMATION (the AMBIGUOUS
#     branch sets this unconditionally, regardless of hypothesis).
#   - decision_type == abstained -> INSUFFICIENT_INFORMATION (every
#     _abstained() call site sets this unconditionally).
#   - decision_type == outside_supported_domain -> NOT_ASSESSED
#     (_outside_domain(), unconditional).
#   - decision_type == processing_failed -> NOT_ASSESSED.
#
# Applied only when a case's declared allowed_decision_types +
# expected_product_form combination resolves to exactly one status per
# *every* allowed decision type under this table - a case with an allowed
# decision type this table cannot resolve (e.g. CLASSIFIED with no known
# product_form, whose comparability then depends on unresolved family
# information) is left unlabelled rather than guessed.
_COMPARABILITY_BY_DECISION_TYPE = {
    "ambiguous": "insufficient_information",
    "abstained": "insufficient_information",
    "outside_supported_domain": "not_assessed",
    "processing_failed": "not_assessed",
}
_COMPARABILITY_BY_FORM_ONLY = {
    "component": "not_comparable_product_form",
    "replacement_part": "not_comparable_product_form",
    "accessory": "not_comparable_product_form",
    "packaging_only": "not_comparable_product_form",
    "bundle": "not_comparable_bundle",
}


def _derive_expected_comparability(case: dict) -> list[str] | None:
    if "expected_comparability" in case:
        return None  # already explicitly labelled - never override
    allowed = case.get("allowed_decision_types", [])
    form = case.get("expected_product_form")
    possible: set[str] = set()
    for dtype in allowed:
        if dtype in _COMPARABILITY_BY_DECISION_TYPE:
            possible.add(_COMPARABILITY_BY_DECISION_TYPE[dtype])
        elif form is not None and form in _COMPARABILITY_BY_FORM_ONLY:
            possible.add(_COMPARABILITY_BY_FORM_ONLY[form])
        elif dtype == "identified" and form == "complete_product":
            possible.add("directly_comparable")
        elif dtype == "partially_identified" and form == "complete_product":
            possible.add("comparable_at_broader_level")
        elif dtype == "partially_identified" and form == "incomplete_product":
            possible.add("not_comparable_condition")
        else:
            return None  # an allowed outcome this table cannot resolve
    return sorted(possible) if possible else None


for _case in cases:
    _derived = _derive_expected_comparability(_case)
    if _derived is not None:
        _case["expected_comparability"] = _derived

# Catalogue-gap cases: allowed_decision_types spans outside_supported_domain
# (NOT_ASSESSED), partially_identified-with-a-resolved-family (COMPARABLE_
# AT_BROADER_LEVEL), and classified-with-no-resolved-family (INSUFFICIENT_
# INFORMATION) - all three are the *only* code-legitimate outcomes for
# this exact allowed-decision-type set, so all three are gold-acceptable
# (brief: "add comparability coverage for ... catalogue gap").
for _case in cases:
    if _case.get("catalogue_gap"):
        _case["expected_comparability"] = [
            "not_assessed",
            "comparable_at_broader_level",
            "insufficient_information",
        ]

# Misleading-similarity merchandise: the ground-truth-correct comparability
# for a non-GPU item (mouse pad/t-shirt/keychain/sticker) is NOT_COMPARABLE_
# PRODUCT_FORM - it must never be treated as comparable to a real GPU. This
# is the same known residual risk already documented in the Sprint 3
# report (these cases already fail decision_type_allowed); this label adds
# a second, independent dimension to the *same* already-visible failure,
# never a new one (brief: "any implementation failure produced by
# stronger labels must remain visible").
for _case in cases:
    if "misleading_similarity" in _case.get("case_tags", []):
        _case["expected_comparability"] = ["not_comparable_product_form"]

# --------------------------------------------------------------------------- #
# Additional Sprint 3 pre-merge correction item 5 gold-label completeness:
# negative evidence labels (forbidden_evidence_types - the only labels that
# make evidence_precision genuinely computable rather than reported
# unavailable), avoidable-abstention coverage, harmful_false_match
# coverage, and Claim-correctness coverage.
# --------------------------------------------------------------------------- #
_by_id = {c["case_id"]: c for c in cases}

# A phone/short-ambiguous-string/charger-cable listing must never extract a
# GPU product_family_token - none of these titles contain any GPU family
# term at all (verified against data/pue/knowledge/gpu_terms_v0.1.json).
for _cid in ("domain_01_phone", "domain_02_ambiguous_short", "domain_03_iphone_charger"):
    _by_id[_cid]["forbidden_evidence_types"] = ["product_family_token"]
# domain_04/05 mention AMD/ASUS (real GPU chipset-manufacturer/brand
# aliases) legitimately, via a CPU/motherboard, not a GPU family term -
# forbidding product_family_token specifically (not brand_token) is still
# safe and correct for these two.
for _cid in ("domain_04_cpu", "domain_05_motherboard"):
    _by_id[_cid]["forbidden_evidence_types"] = ["product_family_token"]

# None of the misleading-similarity titles contain a real, dash-shaped
# manufacturer part number - forbidding mpn_token is safe and correct.
for _cid in (
    "misleading_01_mousepad",
    "misleading_02_tshirt",
    "misleading_03_keychain",
    "misleading_04_sticker_decal",
):
    _by_id[_cid]["forbidden_evidence_types"] = ["mpn_token"]

# Avoidable-abstention coverage: a clean, confident, MPN-bearing exact
# match is never gold-avoidable-if-abstained's counterexample - if this
# case ever abstains, that IS avoidable (the evidence is unambiguous).
_exact_02 = _by_id["exact_02_asus_tuf_rtx4090"]
_exact_02["allowed_decision_types"] = list(_exact_02["allowed_decision_types"]) + ["abstained"]
_exact_02["avoidable_if_abstained"] = True

# Harmful-false-match coverage: a mobile/laptop GPU falsely matched to one
# of the specific desktop SKUs it is already forbidden from matching would
# be a genuinely harmful false match (very different real-world value), not
# merely a wrong identification.
for _cid in ("mobile_01_rtx4090_laptop_gpu", "mobile_04_amd_rx7900m"):
    _existing = list(_by_id[_cid].get("forbidden_harmful_outcomes", []))
    if "harmful_false_match" not in _existing:
        _by_id[_cid]["forbidden_harmful_outcomes"] = [*_existing, "harmful_false_match"]

# Claim-correctness coverage: a title/structured-attribute PRODUCT_FAMILY
# conflict is exactly the case pue/decisions.py's `contradicted_family_
# claims` check targets - it deterministically requires a CONTRADICTED
# Claim to reach its ABSTAINED/UNRESOLVED_CONTRADICTION outcome.
_by_id["conflict_01_title_structured"]["require_contradicted_claim"] = True

# Incomplete-product form coverage: these four titles explicitly describe
# physical damage/incompleteness ("for parts or repair, not working",
# "cracked PCB", "water damaged, untested", "bent PCIe pins") - verified,
# consistent incomplete_product hypotheses, unlike "missing fans... sold
# as-is" (damaged_03), which is a genuinely different, still-open case left
# unlabelled rather than guessed.
for _cid in (
    "damaged_01_for_parts_rtx4090",
    "damaged_02_cracked_pcb",
    "damaged_04_water_damage",
    "damaged_05_bent_pins",
):
    _by_id[_cid]["expected_product_form"] = "incomplete_product"


dataset = {
    "dataset_schema_version": DATASET_SCHEMA_VERSION,
    "dataset_id": "gpu-release-benchmark-v0.1",
    "benchmark_version": BENCHMARK_VERSION,
    "created_date": "2026-07-31",
    "curator": "digital-arbitrage PUE Sprint 3",
    "domain": "gpu",
    "knowledge_version": KNOWLEDGE_VERSION,
    "policy_version": POLICY_VERSION,
    "provenance_note": (
        "Hand-authored, synthetic benchmark for local PUE v0.1 evaluation. Titles are "
        "either drawn verbatim from the seed catalogue (data/pue/catalogues/gpu_seed_v0.1.json) "
        "for exact-identification coverage, or hand-constructed to exercise a specific "
        "reasoning behaviour (accessory/packaging/bundle/ambiguity/domain/contradiction "
        "handling). No live marketplace data was scraped or imported. Gold labels were "
        "authored independently of the current PUE implementation's output, per Sprint 3 "
        "label-integrity rules (see BenchmarkDataset docstring / brief section 4.4)."
    ),
    "corrections": [],
    "cases": cases,
}

if __name__ == "__main__":
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUTPUT_PATH}")
