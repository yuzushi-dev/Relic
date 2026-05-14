"""Tests for Telegram delivery config TUI step."""
import pytest
from io import StringIO
from relic.profile._bootstrap_steps.delivery_config import (
    collect_delivery_config,
    _ask_yes_no,
    _ENV_RE,
)


class TestEnvVarRegex:
    """Tests for env var name validation."""

    @pytest.mark.parametrize("valid", [
        "GUMI_BOT_TOKEN",
        "MY_TOKEN",
        "TELEGRAM_BOT_TOKEN_123",
        "A",
        "X1",
        "MY_VAR_NAME_HERE",
    ])
    def test_valid_env_names(self, valid):
        assert _ENV_RE.match(valid)

    @pytest.mark.parametrize("invalid", [
        "gumi_bot_token",      # lowercase start
        "2MY_TOKEN",           # digit start
        "_MY_TOKEN",           # underscore start
        "my-token",            # hyphen
        "my token",            # space
        "",                    # empty
        "MY TOKEN",            # space in name
    ])
    def test_invalid_env_names(self, invalid):
        assert not _ENV_RE.match(invalid)


class TestAskYesNo:
    """Tests for yes/no prompt."""

    def test_yes_accepted(self):
        inp = StringIO("yes\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=False) is True

    def test_y_accepted(self):
        inp = StringIO("y\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=False) is True

    def test_si_accepted(self):
        inp = StringIO("si\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=False) is True

    def test_no_accepted(self):
        inp = StringIO("no\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=True) is False

    def test_n_accepted(self):
        inp = StringIO("n\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=True) is False

    def test_empty_returns_default(self):
        inp = StringIO("\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=True) is True
        assert _ask_yes_no(inp, out, "Test?", default=False) is False

    def test_invalid_then_valid(self):
        inp = StringIO("maybe\ny\n")
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=False) is True

    def test_eof_returns_default(self):
        inp = StringIO()
        out = StringIO()
        assert _ask_yes_no(inp, out, "Test?", default=True) is True


class TestCollectDeliveryConfig:
    """Tests for full delivery config flow."""

    def test_delivery_disabled_when_no_consent(self):
        consent = {"delivery": False}
        inp = StringIO()
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is False
        output = out.getvalue()
        assert "not configured" in output.lower()

    def test_delivery_disabled_when_consent_absent(self):
        consent = {}
        inp = StringIO()
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is False

    def test_skip_configure(self):
        """User chooses not to configure now."""
        consent = {"delivery": True}
        # "n" = don't configure now
        inp = StringIO("n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is False
        output = out.getvalue()
        assert "skipped" in output.lower()

    def test_full_configure_with_defaults(self):
        """User configures Telegram with default quiet hours, skips token value."""
        consent = {"delivery": True}
        # y=configure, user_id, skip token, then defaults for rest
        inp = StringIO("y\n123456789\n\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is True
        assert result["telegram_user_id"] == "123456789"
        assert result["bot_token_env"] == "GUMI_BOT_TOKEN"  # auto-set from no subject_id
        assert result["contact_channel"] == "telegram"
        assert result["quiet_hours"]["start"] == "22:00"
        assert result["quiet_hours"]["end"] == "08:00"

    def test_full_configure_with_custom_values(self):
        """User configures with custom values, skips token value."""
        consent = {"delivery": True}
        inp = StringIO(
            "y\n"                   # configure now
            "987654321\n"           # user id
            "\n"                    # skip token value
            "23:00\n"               # quiet start
            "07:00\n"               # quiet end
            "America/New_York\n"    # timezone
            "09:00-11:00\n"         # delivery window 1
            "19:00-21:00\n"         # delivery window 2
        )
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is True
        assert result["telegram_user_id"] == "987654321"
        assert result["bot_token_env"] == "GUMI_BOT_TOKEN"  # auto-set
        assert result["quiet_hours"]["start"] == "23:00"
        assert result["quiet_hours"]["end"] == "07:00"
        assert result["quiet_hours"]["timezone"] == "America/New_York"
        assert result["delivery_windows"][0]["start"] == "09:00"
        assert result["delivery_windows"][1]["start"] == "19:00"

    def test_full_configure_with_token_value(self):
        """User enters bot token value — it is exported to os.environ under auto env name."""
        import os
        consent = {"delivery": True}
        auto_env = "GUMI_BOT_TOKEN"
        os.environ.pop(auto_env, None)
        inp = StringIO(f"y\n123456789\n123456789:ABCdefGhIJKlmnopqrstu\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is True
        assert os.environ.get(auto_env) == "123456789:ABCdefGhIJKlmnopqrstu"
        os.environ.pop(auto_env, None)

    def test_invalid_user_id_retry(self):
        """User enters invalid user ID, then valid one."""
        consent = {"delivery": True}
        inp = StringIO("y\nnot_a_number\nabc\n123456789\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        assert result["delivery_enabled"] is True
        assert result["telegram_user_id"] == "123456789"
        output = out.getvalue()
        assert "valid numeric" in output.lower()

    def test_env_name_auto_set_no_prompt(self):
        """Env var name is auto-set from subject_id — no user input required."""
        consent = {"delivery": True}
        inp = StringIO("y\n123456789\n\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent, subject_id="mysubj")
        assert result["bot_token_env"] == "GUMI_MYSUBJ_BOT_TOKEN"

    def test_eof_handling(self):
        """EOF during input returns safe defaults."""
        consent = {"delivery": True}
        inp = StringIO()  # Empty = EOF immediately
        out = StringIO()
        result = collect_delivery_config(inp, out, consent)
        # Should not crash, returns False or partial config
        assert "delivery_enabled" in result

    def test_skip_shows_configure_later_message(self):
        """When skipping, verify the configure-later message is shown."""
        consent = {"delivery": True}
        inp = StringIO("n\n")
        out = StringIO()
        collect_delivery_config(inp, out, consent)
        output = out.getvalue()
        # The skip option text mentions configure later
        assert "relic profile hermes configure-telegram" in output

    def test_configure_now_shows_steps(self):
        """When configuring, step-by-step guidance is shown."""
        consent = {"delivery": True}
        inp = StringIO("y\n123456789\n\n\n\n\n\n")
        out = StringIO()
        collect_delivery_config(inp, out, consent)
        output = out.getvalue()
        assert "STEP 1" in output
        assert "STEP 2" in output
        assert "STEP 3" in output

    def test_successful_config_shows_token_instruction(self):
        """After config, show auto env var name."""
        consent = {"delivery": True}
        inp = StringIO("y\n123456789\n\n\n\n\n\n")
        out = StringIO()
        collect_delivery_config(inp, out, consent)
        output = out.getvalue()
        assert "GUMI_BOT_TOKEN" in output

    def test_auto_generated_env_from_subject_id(self):
        """When subject_id is provided, env var is auto-generated from it."""
        consent = {"delivery": True}
        inp = StringIO("y\n123456789\n\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent, subject_id="subj_test_123")
        output = out.getvalue()
        assert "GUMI_SUBJ_TEST_123_BOT_TOKEN" in output or "GUMI_SUBJ_TEST_123" in output
        assert result["delivery_enabled"] is True

    def test_empty_subject_id_uses_default(self):
        """When no subject_id, uses generic default."""
        consent = {"delivery": True}
        inp = StringIO("y\n123456789\n\n\n\n\n\n\n")
        out = StringIO()
        result = collect_delivery_config(inp, out, consent, subject_id="")
        output = out.getvalue()
        assert "GUMI_BOT_TOKEN" in output
