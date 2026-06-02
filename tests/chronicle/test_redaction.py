"""Tests for relic.chronicle.redaction, T012."""
from __future__ import annotations

import pytest

from relic.chronicle.redaction import (
    SECRET_PATTERNS,
    contains_secret,
    redact_payload,
    redact_string,
)


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------
class TestModuleLevel:
    def test_secret_patterns_compiled(self) -> None:
        assert len(SECRET_PATTERNS) >= 8

    def test_secret_patterns_are_compiled(self) -> None:
        import re

        for p in SECRET_PATTERNS:
            assert isinstance(p, re.Pattern)


# ---------------------------------------------------------------------------
# contains_secret
# ---------------------------------------------------------------------------
class TestContainsSecret:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("my api_key = abcdefghijklmnop", True),
            ("api-key: abcdefghijklmnopqrstuvwxyz", True),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", True),
            ("-----BEGIN RSA PRIVATE KEY-----", True),
            ("password: supersecretpassword", True),
            ("sk-abcdefghijklmnopqrstuvwxyz", True),
            ("ghp_abcdefghijklmnopqrstuvwxyz1234567890ab", True),
            ("user@example.com", True),
            ("xoxb-1234567890123-1234567890123-AbCdEfGhIjKlM", True),
            # Negative cases
            ("hello world", False),
            ("api_key = short", False),  # too short
            ("password: <8c", False),  # too short
            ("", False),
        ],
    )
    def test_contains_secret(self, text: str, expected: bool) -> None:
        assert contains_secret(text) is expected

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"key": "api_key: abcdefghijklmnop"}, True),
            ({"data": {"nested": "ghp_abcdefghijklmnopqrstuvwxyz1234567890ab"}}, True),
            ({"safe": "no secrets here"}, False),
        ],
    )
    def test_contains_secret_dict(self, payload: dict, expected: bool) -> None:
        assert contains_secret(payload) is expected

    def test_contains_secret_bytes(self) -> None:
        assert contains_secret(b"sk-abcdefghijklmnopqrstuvwxyz") is True
        assert contains_secret(b"no secret") is False

    def test_contains_secret_fail_open(self) -> None:
        assert contains_secret(12345) is False

    def test_contains_secret_empty_dict(self) -> None:
        assert contains_secret({}) is False


# ---------------------------------------------------------------------------
# redact_string
# ---------------------------------------------------------------------------
class TestRedactString:
    def test_redact_api_key(self) -> None:
        text = "api_key = mysecretapikey12345678"
        result = redact_string(text)
        assert "mysecretapikey12345678" not in result
        assert "[REDACTED-api_key]" in result

    def test_redact_bearer_token(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc"
        result = redact_string(text)
        assert "[REDACTED-bearer_token]" in result

    def test_redact_pem_key(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQ...\n-----END RSA PRIVATE KEY-----"
        result = redact_string(text)
        assert "[REDACTED-pem_private_key]" in result

    def test_redact_password(self) -> None:
        text = "password: MySecretPass123"
        result = redact_string(text)
        assert "[REDACTED-password]" in result

    def test_redact_openai_key(self) -> None:
        text = "sk-abcdefghijklmnopqrstuvwxyz"
        result = redact_string(text)
        assert "[REDACTED-openai_key]" in result

    def test_redact_github_token(self) -> None:
        token = "ghp_abcdefghijklmnopqrstuvwxyz1234567890ab"
        result = redact_string(token)
        assert token not in result
        assert "[REDACTED-github_token]" in result

    def test_redact_email(self) -> None:
        text = "Contact: user@example.com for info"
        result = redact_string(text)
        assert "[REDACTED-email]" in result

    def test_redact_slack_token(self) -> None:
        text = "xoxb-1234567890123-1234567890123-AbCdEfGhIjKlM"
        result = redact_string(text)
        assert "[REDACTED-slack_token]" in result

    def test_redact_no_match_returns_original(self) -> None:
        text = "hello world, nothing to redact"
        assert redact_string(text) == text

    def test_redact_multiple_matches(self) -> None:
        text = "api_key: abcdefghijklmnop sk-xyzabcdefghijklmnopqrst"
        result = redact_string(text)
        assert "[REDACTED-api_key]" in result
        assert "[REDACTED-openai_key]" in result

    def test_redact_preserves_remaining_text(self) -> None:
        text = "prefix api_key: secret1234567890 suffix"
        result = redact_string(text)
        assert "prefix" in result
        assert "suffix" in result


# ---------------------------------------------------------------------------
# redact_payload
# ---------------------------------------------------------------------------
class TestRedactPayload:
    def test_redact_returns_new_dict(self) -> None:
        original = {"key": "value"}
        result = redact_payload(original)
        assert result is not original

    def test_redact_nested_dict_formatted_string(self) -> None:
        # Secrets stored as "api_key: value" string: pattern matches the label+separator
        payload = {
            "config": {
                "credentials": "api_key: supersecretkey1234567890",
                "host": "localhost",
            }
        }
        result = redact_payload(payload)
        assert "[REDACTED-api_key]" in str(result)
        assert "localhost" in str(result)

    def test_redact_list_of_strings(self) -> None:
        payload = {"items": ["api_key: abcdefghijklmnop", "safe value"]}
        result = redact_payload(payload)
        assert "[REDACTED-api_key]" in result["items"][0]
        assert result["items"][1] == "safe value"

    def test_redact_list_of_dicts(self) -> None:
        payload = {
            "requests": [
                {"header": "Authorization: Bearer validtoken1234567890ab"},
                {"method": "GET"},
            ]
        }
        result = redact_payload(payload)
        assert "[REDACTED-bearer_token]" in str(result)
        assert "GET" in str(result)

    def test_redact_non_string_values_preserved(self) -> None:
        payload = {
            "count": 42,
            "enabled": True,
            "ratio": 3.14,
            "null": None,
        }
        result = redact_payload(payload)
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["ratio"] == 3.14
        assert result["null"] is None

    def test_redact_bytes_value(self) -> None:
        payload = {"token": b"sk-abcdefghijklmnopqrstuvwxyz"}
        result = redact_payload(payload)
        assert isinstance(result["token"], bytes)
        assert b"sk-abcdef" not in result["token"]
        assert b"[REDACTED-" in result["token"]

    def test_redact_empty_dict(self) -> None:
        assert redact_payload({}) == {}

    def test_redact_mixed_realistic_payload(self) -> None:
        # Secrets formatted as labeled strings so patterns can match them
        payload = {
            "event_type": "api_call",
            "metadata": {
                "credentials": "api_key: my_secret_api_key_12345678",
                "request_id": "req-12345",
            },
            "body": {
                "message": "User john@example.com sent a request",
                "configs": [
                    {"auth": "password: SecretPass99", "enabled": True},
                    {"region": "us-east-1"},
                ],
            },
            "count": 1,
        }
        result = redact_payload(payload)
        assert "[REDACTED-api_key]" in str(result)
        assert "[REDACTED-email]" in str(result)
        assert "[REDACTED-password]" in str(result)
        assert "req-12345" in str(result)
        assert "us-east-1" in str(result)
        assert result["count"] == 1
        assert result["body"]["configs"][1]["region"] == "us-east-1"

    def test_redact_fail_open_returns_copy(self) -> None:
        import unittest.mock
        import relic.chronicle.redaction as redmod

        bad_redact = __import__("unittest.mock", fromlist=["mock"]).MagicMock(
            side_effect=RuntimeError("synthetic error")
        )
        with unittest.mock.patch.object(redmod, "redact_string", bad_redact):
            payload = {"key": "value"}
            result = redact_payload(payload)
            assert isinstance(result, dict)
            assert result == {"key": "value"}
