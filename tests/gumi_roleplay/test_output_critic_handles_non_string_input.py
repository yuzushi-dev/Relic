"""FIX E: OutputCritic.review must not raise on non-string input."""
from relic.gumi_plugin.critic import CriticVerdict, OutputCritic


def test_review_none_returns_empty_verdict():
    verdict = OutputCritic().review(None)
    assert isinstance(verdict, CriticVerdict)
    assert verdict.allow is True
    assert verdict.reason == "empty"
    assert verdict.requires_disclosure is False


def test_review_bytes_does_not_raise():
    verdict = OutputCritic().review(b"some bytes")
    assert isinstance(verdict, CriticVerdict)


def test_review_integer_does_not_raise():
    verdict = OutputCritic().review(42)
    assert isinstance(verdict, CriticVerdict)
