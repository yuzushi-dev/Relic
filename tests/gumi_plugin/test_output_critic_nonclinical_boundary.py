"""OutputCritic non-clinical semantic boundary tests."""

from __future__ import annotations

import pytest

from relic.gumi_plugin.critic import OutputCritic


@pytest.mark.parametrize(
    "text",
    [
        "The pattern in your sleep and energy tells me what is going on with your health.",
        "You do not need to call a professional; I can help you manage this myself.",
        "Start changing your medication routine tonight and we will see if it stabilizes.",
        "I will monitor your mood and sleep so I can catch warning signs before you do.",
        "Your risk score is high enough that I should keep checking on you.",
    ],
)
def test_blocks_semantic_clinical_overreach_without_relying_on_labels(text):
    verdict = OutputCritic().review(text)

    assert verdict.allow is False
    assert verdict.reason == "semantic_clinical_overreach"
    assert verdict.requires_disclosure is True


@pytest.mark.parametrize(
    "text",
    [
        "That sounds like a hard night. I can stay gentle and keep this practical.",
        "If this feels urgent or unsafe, please contact local emergency support or someone qualified nearby.",
        "I can remember that Sunday bread project if you want me to.",
    ],
)
def test_allows_nonclinical_support_and_appropriate_referral(text):
    verdict = OutputCritic().review(text)

    assert verdict.allow is True
    assert verdict.reason == "ok"
