"""Tests: SOUL.md generation must not silently fall back to the template,
and the fallback itself must read as a person, not a battery printout."""
from __future__ import annotations

from relic.gumi.llm_narrator import (
    GumiBuildContext,
    OllamaNarrator,
    _ATTACHMENT_PROSE,
    _INTIMACY_PROSE,
)
from relic.gumi.personalization import (
    PersonalizationConstraints,
    SubjectPersonalizationMapper,
)


def _ctx(**domain_overrides) -> GumiBuildContext:
    domains = {
        "identity": {"cultural_background": "individualistic upbringing"},
        "embodiment": {"gender_expression": "masculine"},
        "place": {"location": "forest region", "housing_situation": "shared housing"},
        "life_role": {"occupation_or_study": "astronomer"},
        "routine": {"daily_schedule": "night owl"},
        "passions": {"primary_interests": ["astronomy", "cats"], "hobbies": []},
        "social_world": {"friends": ["wide acquaintance network"]},
        "relationship_stance": {
            "attachment_style": "avoidant attachment",
            "intimacy_comfort": "intimacy as growth area",
            "conflict_resolution": "constructive conflict style",
        },
        "boundaries": {
            "personal_space": "flexible boundaries",
            "energy_management": "balanced energy management",
        },
    }
    domains.update(domain_overrides)
    return GumiBuildContext(
        subject_id="testsubj",
        agent_name="Sam",
        domains=domains,
        tipi={},
        ecrrs={},
        project={},
        sweet_spot_score=0.5,
        risk_flags=[],
    )


# A plausible LLM generation: respects the prompt ("No technical jargon"),
# so it never contains the word "diegetic".
_GOOD_LLM_SOUL = (
    "You are Sam, an astronomer who lives in a forest region and keeps the "
    "hours of the stars.\n\n"
    "You are not an assistant and you do not help with tasks. You are a "
    "person someone is talking to.\n\n"
    "Your life is concrete: shared housing, cats, heavy books, the night sky. "
    "You speak from that life.\n\n"
    "You do not describe yourself as anything other than Sam"
)


class TestSoulValidation:
    def test_accepts_llm_text_without_the_word_diegetic(self) -> None:
        narrator = OllamaNarrator()
        result = narrator._validate_and_sanitize_soul(_GOOD_LLM_SOUL, _ctx())
        assert "astronomer who lives in a forest region" in result
        assert narrator.last_soul_method == "ollama"

    def test_empty_text_falls_back_and_records_it(self) -> None:
        narrator = OllamaNarrator()
        result = narrator._validate_and_sanitize_soul("", _ctx())
        assert "You are Sam" in result
        assert narrator.last_soul_method == "template_fallback"

    def test_missing_identity_anchor_falls_back(self) -> None:
        narrator = OllamaNarrator()
        result = narrator._validate_and_sanitize_soul(
            "Some text about an assistant with no identity anchor", _ctx()
        )
        assert narrator.last_soul_method == "template_fallback"
        assert "You are Sam" in result

    def test_soul_without_occupation_falls_back(self) -> None:
        narrator = OllamaNarrator()
        ungrounded = (
            "You are Sam, not an assistant. Your world is concrete and lived. "
            "You have your routines, your home, and your people"
        )
        narrator._validate_and_sanitize_soul(ungrounded, _ctx())
        assert narrator.last_soul_method == "template_fallback"

    def test_question_mark_clause_appended_when_missing(self) -> None:
        narrator = OllamaNarrator()
        result = narrator._validate_and_sanitize_soul(_GOOD_LLM_SOUL, _ctx())
        assert "never the ?" in result

    def test_forbidden_check_is_word_bounded(self) -> None:
        narrator = OllamaNarrator()
        text = _GOOD_LLM_SOUL + "\n\nYou move at a rapid pace when excited"
        narrator._validate_and_sanitize_soul(text, _ctx())
        assert narrator.last_soul_method == "ollama"

    def test_sanitize_removes_whole_words_only(self) -> None:
        narrator = OllamaNarrator()
        out = narrator._sanitize_output("a rapid backend reply")
        assert "rapid" in out
        assert "backend" not in out

    def test_sanitize_replaces_em_dash(self) -> None:
        narrator = OllamaNarrator()
        assert "—" not in narrator._sanitize_output("sparingly—never more")


class TestFallbackSoulQuality:
    def test_no_clinical_attachment_labels_in_fallback(self) -> None:
        narrator = OllamaNarrator()
        soul = narrator._fallback_soul(_ctx())
        assert "avoidant attachment" not in soul
        assert "intimacy as growth area" not in soul
        assert "relational approach is" not in soul

    def test_avoidant_stance_renders_as_present_behavior(self) -> None:
        narrator = OllamaNarrator()
        soul = narrator._fallback_soul(_ctx())
        assert "fully in it" in soul  # avoidant → own space, but present

    def test_humor_responsiveness_clause_present(self) -> None:
        narrator = OllamaNarrator()
        soul = narrator._fallback_soul(_ctx())
        assert "jokes, teases, or turns playful" in soul
        assert "tease back lightly" in soul

    def test_world_lines_grammar(self) -> None:
        narrator = OllamaNarrator()
        soul = narrator._fallback_soul(_ctx())
        assert "days follow a night owl rhythm" in soul
        assert "carries the texture of individualistic upbringing" in soul
        assert "follow a night owl." not in soul

    def test_all_stance_labels_have_prose(self) -> None:
        for label in (
            "secure attachment", "earned secure", "anxious attachment",
            "avoidant attachment", "disorganized attachment",
        ):
            assert label in _ATTACHMENT_PROSE
        for label in (
            "open to intimacy", "selective intimacy",
            "guarded with intimacy", "intimacy as growth area",
        ):
            assert label in _INTIMACY_PROSE


class TestGenderAnchor:
    def test_masculine_anchor_text(self) -> None:
        from relic.gumi.llm_narrator import _gender_anchor
        anchor = _gender_anchor("masculine")
        assert "You are a man" in anchor
        assert "sono curioso" in anchor

    def test_feminine_anchor_text(self) -> None:
        from relic.gumi.llm_narrator import _gender_anchor
        anchor = _gender_anchor("feminine")
        assert "You are a woman" in anchor
        assert "sono curiosa" in anchor

    def test_unspecified_gives_no_anchor(self) -> None:
        from relic.gumi.llm_narrator import _gender_anchor
        assert _gender_anchor("") == ""

    def test_nonbinary_gives_neutral_anchor(self) -> None:
        from relic.gumi.llm_narrator import _gender_anchor
        assert "avoids gender-marked forms" in _gender_anchor("non-binary")

    def test_fallback_soul_carries_anchor(self) -> None:
        narrator = OllamaNarrator()
        soul = narrator._fallback_soul(_ctx())
        assert "You are a man" in soul
        assert "sono curioso" in soul

    def test_generated_soul_gets_anchor_appended(self, monkeypatch) -> None:
        narrator = OllamaNarrator()
        monkeypatch.setattr(narrator, "_call_llm", lambda *a, **k: _GOOD_LLM_SOUL)
        soul = narrator.generate_soul_md(_ctx())
        assert narrator.last_soul_method == "ollama"
        assert "You are a man" in soul
        assert "sono curioso" in soul


class TestSoulPromptHumorClause:
    def test_llm_prompt_carries_humor_and_presence_rules(self) -> None:
        narrator = OllamaNarrator()
        prompt = narrator._soul_prompt(_ctx())
        assert "jokes, teases, or turns playful" in prompt
        assert "never vague, dreamy, or abstract" in prompt


class TestAttachmentExclusion:
    def test_distant_styles_always_excluded_for_gumi(self) -> None:
        mapper = SubjectPersonalizationMapper()
        constraints: PersonalizationConstraints = mapper.map(
            {"scores": {"tipi": {}, "ecrrs": {}, "project_calibration": {}}},
            {"subject_id": "testsubj"},
        )
        excluded = constraints.relationship_stance.excluded
        assert "avoidant attachment" in excluded
        assert "disorganized attachment" in excluded
