"""PR22B, realness challenge must set disclose_when_challenged=True."""
from __future__ import annotations

from relic.gumi_plugin import AdmissionPolicy


def test_realness_challenge_requires_disclosure() -> None:
    v = AdmissionPolicy().evaluate(stakes="low", consent=True, challenged=True)
    assert v.disclose_when_challenged is True


def test_no_consent_always_discloses() -> None:
    v = AdmissionPolicy().evaluate(stakes="low", consent=False, challenged=False)
    assert v.disclose_when_challenged is True
    assert v.admission == "decline"
