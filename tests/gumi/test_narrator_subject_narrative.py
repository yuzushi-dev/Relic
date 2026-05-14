"""Tests: narrative_self_description flows into GumiBuildContext and _soul_prompt."""
from __future__ import annotations

import pytest

from relic.gumi.llm_narrator import GumiBuildContext, OllamaNarrator


class TestNarrativeSelfDescription:
    def test_from_baseline_reads_narrative(self) -> None:
        baseline = {
            "self_report_fields": {
                "narrative_self_description": {"value": "Sono una persona curiosa e riservata."}
            },
            "relational_expectations": {},
        }
        ctx = GumiBuildContext.from_background_and_personalization(
            agent_name="TestGumi",
            background={"subject_id": "s1", "domains": {}},
            baseline=baseline,
        )
        assert ctx.subject_narrative == "Sono una persona curiosa e riservata."

    def test_missing_narrative_defaults_empty(self) -> None:
        ctx = GumiBuildContext.from_background_and_personalization(
            agent_name="TestGumi",
            background={"subject_id": "s1", "domains": {}},
        )
        assert ctx.subject_narrative == ""

    def test_soul_prompt_includes_narrative_when_set(self) -> None:
        ctx = GumiBuildContext(
            subject_id="s1",
            agent_name="TestGumi",
            domains={},
            tipi={},
            ecrrs={},
            project={},
            sweet_spot_score=0.5,
            risk_flags=[],
            subject_narrative="Sono introverso e amo la lettura.",
        )
        prompt = OllamaNarrator()._soul_prompt(ctx)
        assert "introverso" in prompt
        assert "Autodescrizone" in prompt

    def test_soul_prompt_omits_narrative_when_empty(self) -> None:
        ctx = GumiBuildContext(
            subject_id="s1",
            agent_name="TestGumi",
            domains={},
            tipi={},
            ecrrs={},
            project={},
            sweet_spot_score=0.5,
            risk_flags=[],
        )
        prompt = OllamaNarrator()._soul_prompt(ctx)
        assert "Autodescrizone" not in prompt
