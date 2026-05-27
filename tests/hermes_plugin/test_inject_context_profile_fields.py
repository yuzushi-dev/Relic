"""Tests: inject_context wires profile fields into PromptContextPack.

Covers:
- preferred_name lands in USER_PRIVATE_FACTS
- preferred_topics / avoided_topics appear in injected context
- continuity_expectations / role_expectations_for_gumi appear in injected context
- No raw profile data leaks via _RAW_PROMPT_LEAK_MARKERS
- inject_context returns None gracefully when subject profile unreadable
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from relic.hermes_plugin.context_injection import (
    inject_context,
    _build_user_private_facts,
    _gender_agreement_directive,
    _load_subject_profile_fields,
)


class TestGenderAgreementDirective:
    @pytest.mark.parametrize("value", ["male", "maschio", "Uomo", "M"])
    def test_masculine_variants(self, value: str) -> None:
        out = _gender_agreement_directive(value)
        assert out is not None and "maschile" in out and "lui" in out

    @pytest.mark.parametrize("value", ["female", "femmina", "Donna", "F"])
    def test_feminine_variants(self, value: str) -> None:
        out = _gender_agreement_directive(value)
        assert out is not None and "femminile" in out and "lei" in out

    @pytest.mark.parametrize("value", ["non-binary", "non binario", "genderqueer", "agender"])
    def test_nonbinary_stays_neutral(self, value: str) -> None:
        out = _gender_agreement_directive(value)
        assert out is not None and "non binario" in out
        assert "lui" not in out and "lei" not in out

    def test_unknown_value_surfaced_neutral(self) -> None:
        out = _gender_agreement_directive("two-spirit")
        assert out is not None and "two-spirit" in out and "neutre" in out

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_returns_none(self, value: str | None) -> None:
        assert _gender_agreement_directive(value) is None

    @pytest.mark.parametrize("p", ["lui", "He/Him"])
    def test_explicit_masculine_pronoun(self, p: str) -> None:
        out = _gender_agreement_directive(None, preferred_pronoun=p)
        assert out is not None and "lui" in out and "maschile" in out

    @pytest.mark.parametrize("p", ["lei", "she/her"])
    def test_explicit_feminine_pronoun(self, p: str) -> None:
        out = _gender_agreement_directive(None, preferred_pronoun=p)
        assert out is not None and "lei" in out and "femminile" in out

    def test_pronoun_overrides_gender_identity(self) -> None:
        # Non-binary identity but explicit "lei" → feminine agreement wins.
        out = _gender_agreement_directive("non-binary", preferred_pronoun="lei")
        assert out is not None and "femminile" in out
        assert "non binario" not in out

    def test_custom_pronoun_surfaced(self) -> None:
        out = _gender_agreement_directive("non-binary", preferred_pronoun="ə")
        assert out is not None and "ə" in out and "neutre" in out

    def test_pronoun_injected_into_private_facts(self) -> None:
        fields = {
            "preferred_name": "Alex",
            "gender_identity": "non-binary",
            "preferred_pronoun": "lui",
            "interaction_preferences": {},
            "relational_expectations": {},
        }
        result = _build_user_private_facts(fields)
        assert "lui" in result and "maschile" in result

    def test_directive_injected_into_private_facts(self) -> None:
        fields = {
            "preferred_name": "Sara",
            "gender_identity": "female",
            "interaction_preferences": {},
            "relational_expectations": {},
        }
        result = _build_user_private_facts(fields)
        assert "femminile" in result and "lei" in result


class TestBuildUserPrivateFacts:
    def test_preferred_name_included(self) -> None:
        fields = {"preferred_name": "Luca", "interaction_preferences": {}, "relational_expectations": {}}
        result = _build_user_private_facts(fields)
        assert "Luca" in result
        assert "Nome preferito" in result

    def test_language_included(self) -> None:
        fields = {"language": "it", "interaction_preferences": {}, "relational_expectations": {}}
        result = _build_user_private_facts(fields)
        assert "it" in result
        assert "Lingua preferita" in result

    def test_preferred_topics_included(self) -> None:
        fields = {
            "interaction_preferences": {"preferred_topics": ["calcio", "musica"]},
            "relational_expectations": {},
        }
        result = _build_user_private_facts(fields)
        assert "Argomenti graditi" in result
        assert "calcio" in result

    def test_avoided_topics_included(self) -> None:
        fields = {
            "interaction_preferences": {"avoided_topics": ["politica"]},
            "relational_expectations": {},
        }
        result = _build_user_private_facts(fields)
        assert "Argomenti da evitare" in result
        assert "politica" in result

    def test_continuity_expectations_included(self) -> None:
        fields = {
            "interaction_preferences": {},
            "relational_expectations": {"continuity_expectations": "high"},
        }
        result = _build_user_private_facts(fields)
        assert "continuità narrativa" in result
        assert "high" in result

    def test_role_expectations_included(self) -> None:
        fields = {
            "interaction_preferences": {},
            "relational_expectations": {"role_expectations_for_gumi": "amica fidata"},
        }
        result = _build_user_private_facts(fields)
        assert "Ruolo atteso" in result
        assert "amica fidata" in result

    def test_empty_fields_produces_empty_string(self) -> None:
        result = _build_user_private_facts({})
        assert result == ""


class TestInjectContext:
    def test_returns_dict_with_context_key(self) -> None:
        result = inject_context(session_id="test-session", user_message="ciao")
        assert result is not None
        assert "context" in result

    def test_user_message_not_in_output(self) -> None:
        secret = "SECRET_USER_MESSAGE_12345"
        result = inject_context(session_id="s1", user_message=secret)
        assert result is None or secret not in result.get("context", "")

    def test_raw_marker_causes_none(self) -> None:
        """If somehow context text contained a raw marker, inject_context should fail-open (return None)."""
        with patch(
            "relic.hermes_plugin.context_injection._build_user_private_facts",
            return_value="SECRET_RAW_PROMPT_SHOULD_NOT_APPEAR",
        ):
            with patch(
                "relic.hermes_plugin.context_injection._load_subject_profile_fields",
                return_value={"preferred_name": "x"},
            ):
                with patch.dict(os.environ, {"RELIC_SUBJECT_ID": "test-subject"}):
                    result = inject_context(session_id="s1", user_message="hi")
                    assert result is None

    def test_profile_fields_appear_in_context(self, tmp_path: Path) -> None:
        baseline = {
            "preferred_name": "Luca",
            "language": "it",
            "interaction_preferences": {"preferred_topics": ["cinema"]},
            "relational_expectations": {},
        }
        baseline_file = tmp_path / "baseline_user_profile.json"
        baseline_file.write_text(json.dumps(baseline))

        mock_profile = MagicMock()
        mock_profile.relic_subject_home = tmp_path

        with patch("relic.profile.registry.ProfileRegistry") as MockReg:
            MockReg.return_value.get_subject.return_value = mock_profile
            with patch.dict(os.environ, {"RELIC_SUBJECT_ID": "test-subject"}):
                result = inject_context(session_id="s2", user_message="hello")

        assert result is not None
        ctx = result["context"]
        assert "Luca" in ctx
        assert "cinema" in ctx
