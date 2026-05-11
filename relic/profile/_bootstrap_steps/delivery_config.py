"""TUI step: collect Telegram delivery configuration without secrets."""
from __future__ import annotations

import re
from typing import TextIO

from relic.profile._bootstrap_steps._io import prompt_optional

_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _ask_yes_no(io_in: TextIO, io_out: TextIO, question: str, default: bool = False) -> bool:
    """Ask yes/no question using io_in."""
    suffix = "Y/n" if default else "y/N"
    while True:
        print(f"\n  {question}", file=io_out)
        print(f"  Answer ({suffix}): ", end="", flush=True, file=io_out)
        try:
            raw = io_in.readline()
            if raw is None or raw == "":
                return default
            answer = raw.strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes", "s", "si"):
                return True
            if answer in ("n", "no"):
                return False
            print("  Please answer y/n.", file=io_out)
        except (EOFError, OSError):
            return default


def collect_delivery_config(io_in: TextIO, io_out: TextIO, consent_record: dict) -> dict:
    """Collect delivery settings, gated by consent."""
    print("\n" + "=" * 60, file=io_out)
    print("  TELEGRAM DELIVERY SETUP", file=io_out)
    print("=" * 60, file=io_out)
    
    if consent_record.get("delivery") is not True:
        print("\n  Delivery not configured: delivery consent absent.", file=io_out)
        return {"delivery_enabled": False}

    # Step-by-step guide for Telegram setup
    print("\n  To enable Telegram delivery, you need:", file=io_out)
    print("    1. Your Telegram User ID (chat ID)", file=io_out)
    print("    2. A Telegram Bot Token", file=io_out)
    print("", file=io_out)
    
    # Ask if user wants to configure now or skip
    print("  Skip this step if you don't have a bot token yet.", file=io_out)
    print("  You can configure it later with:", file=io_out)
    print("    relic profile hermes configure-telegram", file=io_out)
    
    configure_now = _ask_yes_no(io_in, io_out, "Configure Telegram now?", default=False)
    if not configure_now:
        print("\n  Telegram delivery skipped.", file=io_out)
        return {"delivery_enabled": False}
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 1: Get your Telegram User ID", file=io_out)
    print("-" * 60, file=io_out)
    print("  1. Open Telegram and search for @useridrobot or @UserInfeBot", file=io_out)
    print("  2. Start a chat with the bot and send /start", file=io_out)
    print("  3. The bot will reply with your User ID (a number like 123456789)", file=io_out)
    print("", file=io_out)
    
    telegram_user_id = None
    while telegram_user_id is None:
        raw_id = prompt_optional(
            "telegram_user_id",
            "Your Telegram User ID (number from the bot)",
            io_in,
            io_out,
        )
        if raw_id and raw_id.isdigit():
            telegram_user_id = raw_id
        elif raw_id:
            print("  Please enter a valid numeric User ID.", file=io_out)
        else:
            print("  This field is required.", file=io_out)
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 2: Create a Telegram Bot (if you don't have one)", file=io_out)
    print("-" * 60, file=io_out)
    print("  1. Open Telegram and search for @BotFather", file=io_out)
    print("  2. Send /newbot and follow the prompts", file=io_out)
    print("  3. BotFather will give you a token like: 123456789:ABCdefGhIJKlmn", file=io_out)
    print("  4. Add the bot to your Telegram with /start", file=io_out)
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 3: Enter your Bot Token", file=io_out)
    print("-" * 60, file=io_out)
    print("  Enter the env variable name that will hold your bot token.", file=io_out)
    print("  Example: GUMI_SUBJ_TEST_BOT_TOKEN", file=io_out)
    print("  You will set this with: export GUMI_SUBJ_TEST_BOT_TOKEN=your_token", file=io_out)
    
    bot_token_env = None
    while bot_token_env is None:
        candidate = prompt_optional(
            "bot_token_env",
            "Env variable name for bot token",
            io_in,
            io_out,
        )
        if not candidate:
            print("  This field is required.", file=io_out)
            continue
        if _ENV_RE.match(candidate):
            bot_token_env = candidate
        else:
            print("  Invalid env name. Use uppercase letters, digits, and underscores.", file=io_out)
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 4: Quiet Hours (optional)", file=io_out)
    print("-" * 60, file=io_out)
    quiet_start = prompt_optional("quiet_hours.start", "Quiet hours start", io_in, io_out, default="22:00")
    quiet_end = prompt_optional("quiet_hours.end", "Quiet hours end", io_in, io_out, default="08:00")
    quiet_tz = prompt_optional("quiet_hours.timezone", "Timezone", io_in, io_out, default="Europe/Rome")
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 5: Contact Frequency Limit (optional)", file=io_out)
    print("-" * 60, file=io_out)
    freq_window = prompt_optional("max_contact_frequency.window", "Frequency window (day/week)", io_in, io_out, default="day")
    freq_count_raw = prompt_optional("max_contact_frequency.count", "Max contacts per window", io_in, io_out, default="1")
    try:
        freq_count = int(freq_count_raw) if freq_count_raw else 1
    except ValueError:
        freq_count = 1
    
    enabled = bool(telegram_user_id and bot_token_env)
    
    print("\n" + "=" * 60, file=io_out)
    if enabled:
        print("  Telegram delivery configured!", file=io_out)
        print(f"  User ID: {telegram_user_id}", file=io_out)
        print(f"  Token env: {bot_token_env}", file=io_out)
        print(f"  Next: export {bot_token_env}=YOUR_BOT_TOKEN", file=io_out)
    else:
        print("  Telegram delivery not configured.", file=io_out)
    print("=" * 60, file=io_out)
    
    return {
        "delivery_enabled": enabled,
        "contact_channel": "telegram",
        "telegram_user_id": telegram_user_id,
        "bot_token_env": bot_token_env,
        "quiet_hours": {"start": quiet_start, "end": quiet_end, "timezone": quiet_tz},
        "max_contact_frequency": {"window": freq_window, "count": freq_count},
    }
