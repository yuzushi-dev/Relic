"""Tests: continuity_expectations + role_expectations_for_gumi flow into GumiBuildContext and prompts."""
from __future__ import annotations

import pytest

from relic.gumi.llm_narrator import GumiBuildContext


class TestGumiBuildContextRelationalFields:
    def test_from_background_and_personalization_reads_relational_expectations(self) -> None:
        baseline = {
            "relational_expectations": {
                "continuity_expectations": "high",
                "role_expectations_for_gumi": "amica fidata",
            }
        }
        ctx = GumiBuildContext.from_background_and_personalization(
            agent_name="TestGumi",
            background={"subject_id": "s1", "domains": {}},
            baseline=baseline,
        )
        assert ctx.continuity_expectations == "high"
        assert ctx.role_expectations_for_gumi == "amica fidata"

    def test_missing_relational_expectations_defaults_to_empty(self) -> None:
        ctx = GumiBuildContext.from_background_and_personalization(
            agent_name="TestGumi",
            background={"subject_id": "s1", "domains": {}},
        )
        assert ctx.continuity_expectations == ""
        assert ctx.role_expectations_for_gumi == ""

    def test_soul_prompt_includes_continuity_when_set(self) -> None:
        from relic.gumi.llm_narrator import OllamaNarrator

        ctx = GumiBuildContext(
            subject_id="s1",
            agent_name="TestGumi",
            domains={},
            tipi={},
            ecrrs={},
            project={},
            sweet_spot_score=0.5,
            risk_flags=[],
            continuity_expectations="high",
            role_expectations_for_gumi="amica fidata",
        )
        narrator = OllamaNarrator()
        prompt = narrator._soul_prompt(ctx)
        assert "high" in prompt
        assert "amica fidata" in prompt

    def test_soul_prompt_omits_empty_relational_fields(self) -> None:
        from relic.gumi.llm_narrator import OllamaNarrator

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
        narrator = OllamaNarrator()
        prompt = narrator._soul_prompt(ctx)
        assert "Aspettative di continuità" not in prompt
        assert "Ruolo atteso" not in prompt
