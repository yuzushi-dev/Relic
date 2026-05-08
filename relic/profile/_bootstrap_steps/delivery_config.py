"""TUI step: collect Telegram delivery configuration without secrets."""
from __future__ import annotations

import re
from typing import TextIO

from relic.profile._bootstrap_steps._io import prompt_optional

_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def collect_delivery_config(io_in: TextIO, io_out: TextIO, consent_record: dict) -> dict:
    """Collect delivery settings, gated by consent."""
    print("\n--- Delivery Configuration ---", file=io_out)
    if consent_record.get("delivery") is not True:
        print("Delivery not configured: delivery consent absent.", file=io_out)
        return {"delivery_enabled": False}

    print("Enter identifiers and env variable names only. Do not enter real tokens.", file=io_out)
    telegram_user_id = prompt_optional("telegram_user_id", "Subject Telegram ID/chat.", io_in, io_out)
    bot_token_env = None
    while bot_token_env is None:
        candidate = prompt_optional(
            "bot_token_env",
            "Name of the env variable holding the bot token, e.g. GUMI_SUBJ_TEST_TELEGRAM_BOT_TOKEN.",
            io_in,
            io_out,
        )
        if candidate is None or _ENV_RE.match(candidate):
            bot_token_env = candidate
        else:
            print("  Invalid env name. Use uppercase letters, digits, and underscores.", file=io_out)
    quiet_start = prompt_optional("quiet_hours.start", "Quiet hours start.", io_in, io_out, default="22:00")
    quiet_end = prompt_optional("quiet_hours.end", "Quiet hours end.", io_in, io_out, default="08:00")
    quiet_tz = prompt_optional("quiet_hours.timezone", "Quiet hours timezone, e.g. Europe/Rome.", io_in, io_out, default="UTC")
    freq_window = prompt_optional("max_contact_frequency.window", "Frequency window (day / week).", io_in, io_out, default="day")
    freq_count_raw = prompt_optional("max_contact_frequency.count", "Maximum contacts in window.", io_in, io_out, default="1")
    try:
        freq_count = int(freq_count_raw) if freq_count_raw else 1
    except ValueError:
        freq_count = 1
    enabled = bool(telegram_user_id and bot_token_env)
    return {
        "delivery_enabled": enabled,
        "contact_channel": "telegram",
        "telegram_user_id": telegram_user_id,
        "bot_token_env": bot_token_env,
        "quiet_hours": {"start": quiet_start, "end": quiet_end, "timezone": quiet_tz},
        "max_contact_frequency": {"window": freq_window, "count": freq_count},
    }
