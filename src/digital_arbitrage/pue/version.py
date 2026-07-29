"""Version constants for the PUE v0.1 vertical slice.

Every Reasoning Record embeds these versions (see spec section 7.3) so a
Decision can always be traced back to the exact capability, policy and
knowledge artifacts that produced it.
"""

from __future__ import annotations

#: Reasoning-record schema version.
SCHEMA_VERSION = "0.1"

#: Version of the PUE component/pipeline code itself.
CAPABILITY_VERSION = "pue-0.1.0"

#: Version of the decision policy (thresholds, hard-rejection rules).
POLICY_VERSION = "gpu-policy-0.1.0"

#: Version of the seed catalogue knowledge artifact.
KNOWLEDGE_VERSION = "gpu-seed-0.1.0"

#: Version of the term-group knowledge artifact (product-form/exclusion terms).
TERM_VERSION = "gpu-terms-0.1.0"
