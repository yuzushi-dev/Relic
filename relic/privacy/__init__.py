"""Privacy gateway package per PR04 contract.

The flat ``relic/privacy_gate.py`` module is preserved for backward compatibility
with existing tests; this package adds the modular surface required by
dev_docs/orchestration/ZERO_KNOWLEDGE_PR_FILE_CONTRACTS.md#pr04.
"""

from relic.privacy.gateway import PrivacyGateway, PrivacyDecision
from relic.privacy.policy import PrivacyPolicy, load_policy
from relic.privacy.pii import detect_pii, redact_pii
from relic.privacy.inference import classify_inference
from relic.privacy.trace import PrivacyTrace, write_trace

__all__ = [
    "PrivacyGateway",
    "PrivacyDecision",
    "PrivacyPolicy",
    "load_policy",
    "detect_pii",
    "redact_pii",
    "classify_inference",
    "PrivacyTrace",
    "write_trace",
]
