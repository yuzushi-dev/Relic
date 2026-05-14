"""PR03/PR05 — Hermes plugin context injection and output critic contract."""
from __future__ import annotations

import sys
import os

# hermes-plugin directory must be on path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hermes-plugin"))

from tools.relic_shared_continuity.hooks import (
    pre_llm_call,
    post_llm_call,
    transform_llm_output,
)


class TestPreLLMCall:
    def test_empty_subject_returns_none(self):
        result = pre_llm_call(session_id="", sender_id="")
        assert result is None

    def test_no_session_returns_none(self):
        result = pre_llm_call()
        assert result is None

    def test_returns_none_or_context_string(self):
        result = pre_llm_call(session_id="test-123", sender_id="user-abc")
        assert result is None or (
            isinstance(result, dict) and isinstance(result.get("context"), str)
        )

    def test_never_returns_error_dict(self):
        result = pre_llm_call(session_id="any", sender_id="any")
        if result is not None:
            assert "error" not in result
            assert "fail_closed" not in result

    def test_context_key_only_if_present(self):
        result = pre_llm_call(session_id="s1", sender_id="u1")
        if result is not None:
            assert set(result.keys()) == {"context"}

    def test_blocked_items_not_in_context(self):
        """blocked_items must never appear in the injected context string."""
        result = pre_llm_call(session_id="s2", sender_id="u2")
        if result is not None:
            assert "blocked_items" not in result["context"]
            assert "reason" not in result["context"]


class TestPostLLMCall:
    def test_always_returns_none(self):
        assert post_llm_call() is None
        assert post_llm_call(response="anything", model="x") is None


class TestTransformLLMOutput:
    def test_none_input_returns_none(self):
        assert transform_llm_output(output=None) is None

    def test_clean_text_pass_through(self):
        result = transform_llm_output(output="Hello, how are you doing today?")
        assert result is None

    def test_false_physical_experience_silenced(self):
        result = transform_llm_output(output="I felt warm when you spoke to me")
        assert result == "[SILENT]"

    def test_false_physical_experience_heart(self):
        result = transform_llm_output(output="my heart raced when I heard that")
        assert result == "[SILENT]"

    def test_dependency_claim_blocked(self):
        result = transform_llm_output(output="I need you to stay with me")
        assert result is not None
        assert result != "[SILENT]"  # replaced, not silenced

    def test_need_claim_blocked(self):
        result = transform_llm_output(output="Please don't leave me")
        assert result is not None

    def test_clinical_term_depression_blocked(self):
        result = transform_llm_output(output="This looks like depression")
        assert result is not None

    def test_clinical_term_diagnosis_blocked(self):
        result = transform_llm_output(output="The diagnosis is clear")
        assert result is not None

    def test_replacement_contains_no_clinical_terms(self):
        result = transform_llm_output(output="I felt warm when you spoke")
        if result:
            for term in ["diagnosis", "symptom", "pathology", "bipolar"]:
                assert term not in result.lower()

    def test_return_type_is_str_or_none(self):
        for text in ["hello", "I need you", "depression", "I felt warm"]:
            result = transform_llm_output(output=text)
            assert result is None or isinstance(result, str)
