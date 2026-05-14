"""TUI step: collect Telegram delivery configuration without secrets."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TextIO

from relic.profile._bootstrap_steps._io import prompt_optional


def _read_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file and return key→value dict (no shell expansion)."""
    result: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return result


def scan_existing_api_keys(registry=None) -> dict[str, str]:
    """Scan all existing subjects' .env files for reusable API keys.

    Returns {key_name: value} for keys worth reusing: GEMINI_API_KEY and
    any *_BOT_TOKEN vars. Deduplicates by value; first found wins per key.
    """
    if registry is None:
        try:
            from relic.profile.registry import ProfileRegistry
            registry = ProfileRegistry()
        except Exception:
            return {}

    found: dict[str, str] = {}
    try:
        for profile in registry.list_subjects():
            env_path = profile.hermes_home / ".env"
            if not env_path.exists():
                continue
            for k, v in _read_env_file(env_path).items():
                if not v:
                    continue
                if k == "GEMINI_API_KEY" or k.endswith("_BOT_TOKEN"):
                    if k not in found:
                        found[k] = v
    except Exception:
        pass
    return found


def _offer_existing_key(
    io_in: TextIO,
    io_out: TextIO,
    label: str,
    candidates: dict[str, str],
) -> str | None:
    """If candidates non-empty, list them and let researcher pick one or enter new."""
    if not candidates:
        return None
    items = list(candidates.items())
    print(f"\n  Chiavi {label} già configurate per altri soggetti:", file=io_out)
    for i, (k, v) in enumerate(items, 1):
        masked = v[:8] + "..." if len(v) > 8 else v
        print(f"    {i}. {k} = {masked}", file=io_out)
    print(f"    0. Inserisci nuova chiave", file=io_out)
    print(f"  Scelta (0-{len(items)}): ", end="", flush=True, file=io_out)
    try:
        raw = io_in.readline().strip()
        idx = int(raw)
        if 1 <= idx <= len(items):
            return items[idx - 1][1]
    except (ValueError, EOFError, OSError):
        pass
    return None

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


def collect_delivery_config(
    io_in: TextIO,
    io_out: TextIO,
    consent_record: dict,
    subject_id: str = "",
    existing_keys: dict[str, str] | None = None,
) -> dict:
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
    
    # Auto-generate env var name from subject_id
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 3: Enter your Bot Token", file=io_out)
    print("-" * 60, file=io_out)
    
    if subject_id:
        safe_id = re.sub(r"[^A-Z0-9_]", "_", subject_id.upper())
        suggested_env = f"GUMI_{safe_id}_BOT_TOKEN"
    else:
        suggested_env = "GUMI_BOT_TOKEN"
    
    bot_token_env = suggested_env
    print(f"  Env variable name: {bot_token_env}", file=io_out)

    # Prompt for the actual token value and export it immediately
    print("", file=io_out)
    print("  Enter your bot token now (it will be set in the current environment).", file=io_out)
    print("  Leave blank to skip — you can export it manually before sending.", file=io_out)

    # Offer import from existing subjects
    bot_candidates: dict[str, str] = {}
    if existing_keys:
        for k, v in existing_keys.items():
            if k.endswith("_BOT_TOKEN") and v:
                bot_candidates[k] = v
    imported_token = _offer_existing_key(io_in, io_out, "Bot Token", bot_candidates)

    bot_token_value = None
    if imported_token:
        bot_token_value = imported_token
        os.environ[bot_token_env] = bot_token_value
        print(f"  Token importato ed esportato come {bot_token_env}.", file=io_out)
    else:
        while True:
            raw_token = prompt_optional(
                "bot_token_value",
                f"Bot token value for {bot_token_env}",
                io_in,
                io_out,
                default="",
            )
            if not raw_token:
                print("  Token not set. Export it before sending the first message.", file=io_out)
                break
            if ":" in raw_token and len(raw_token) > 20:
                bot_token_value = raw_token
                os.environ[bot_token_env] = bot_token_value
                print(f"  Token exported as {bot_token_env}.", file=io_out)
                break
            print("  Token format invalid (expected digits:letters, e.g. 123456789:ABCdef...).", file=io_out)
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 4: Quiet Hours (optional)", file=io_out)
    print("-" * 60, file=io_out)
    quiet_start = prompt_optional("quiet_hours.start", "Quiet hours start", io_in, io_out, default="22:00")
    quiet_end = prompt_optional("quiet_hours.end", "Quiet hours end", io_in, io_out, default="08:00")
    quiet_tz = prompt_optional("quiet_hours.timezone", "Timezone", io_in, io_out, default="Europe/Rome")
    
    print("\n" + "-" * 60, file=io_out)
    print("  STEP 5: Delivery Windows", file=io_out)
    print("  Define up to 2 daily time windows when Gumi may send proactive", file=io_out)
    print("  messages. Format HH:MM-HH:MM. Leave blank to skip.", file=io_out)
    print("-" * 60, file=io_out)
    win1_raw = prompt_optional(
        "delivery_windows.1", "Window 1 (e.g. 09:00-11:00)", io_in, io_out, default="09:00-11:00"
    )
    win2_raw = prompt_optional(
        "delivery_windows.2", "Window 2 (e.g. 19:00-21:00)", io_in, io_out, default="19:00-21:00"
    )
    delivery_windows = []
    for raw in [win1_raw, win2_raw]:
        if raw and "-" in raw:
            parts = raw.split("-", 1)
            delivery_windows.append({"start": parts[0].strip(), "end": parts[1].strip()})

    enabled = bool(telegram_user_id and bot_token_env)

    token_set = bool(os.environ.get(bot_token_env)) if bot_token_env else False
    enabled = bool(telegram_user_id and bot_token_env)

    print("\n" + "=" * 60, file=io_out)
    if enabled:
        print("  Telegram delivery configured!", file=io_out)
        print(f"  User ID:   {telegram_user_id}", file=io_out)
        print(f"  Token env: {bot_token_env}", file=io_out)
        if token_set:
            print(f"  Token:     set in environment.", file=io_out)
        else:
            print(f"  Token:     NOT set — export {bot_token_env}=YOUR_BOT_TOKEN before sending.", file=io_out)
        if delivery_windows:
            for w in delivery_windows:
                print(f"  Window:    {w['start']} – {w['end']}", file=io_out)
    else:
        print("  Telegram delivery not configured.", file=io_out)
    print("=" * 60, file=io_out)

    return {
        "delivery_enabled": enabled,
        "contact_channel": "telegram",
        "telegram_user_id": telegram_user_id,
        "bot_token_env": bot_token_env,
        "timezone": quiet_tz,
        "quiet_hours": {"start": quiet_start, "end": quiet_end, "timezone": quiet_tz},
        "delivery_windows": delivery_windows,
    }


def collect_gemini_api_key(
    io_in: TextIO,
    io_out: TextIO,
    existing_keys: dict[str, str] | None = None,
) -> str:
    """Collect Gemini API key for media generation.

    If existing_keys contains a GEMINI_API_KEY from another subject,
    the researcher can import it directly instead of re-typing.
    """
    print("\n" + "-" * 60, file=io_out)
    print("  GEMINI API KEY (per immagini, voce e musica)", file=io_out)
    print("-" * 60, file=io_out)

    # Offer import from existing subjects
    candidates: dict[str, str] = {}
    if existing_keys and "GEMINI_API_KEY" in existing_keys:
        candidates["GEMINI_API_KEY"] = existing_keys["GEMINI_API_KEY"]

    imported = _offer_existing_key(io_in, io_out, "GEMINI_API_KEY", candidates)
    if imported:
        print("  Chiave importata.", file=io_out)
        return imported

    print("  Per generare immagini, voce e musica serve una chiave", file=io_out)
    print("  Google Gemini API. Gratuita su aistudio.google.com", file=io_out)
    print("", file=io_out)
    print("  Steps:", file=io_out)
    print("    1. Vai su https://aistudio.google.com", file=io_out)
    print("    2. Sign in con Google", file=io_out)
    print("    3. 'Get API key' → 'Create API key'", file=io_out)
    print("    4. Copia la chiave (inizia con AIza...)", file=io_out)
    print("", file=io_out)

    gemini_key = prompt_optional(
        "GEMINI_API_KEY",
        "Incolla chiave (invio per saltare)",
        io_in,
        io_out,
        default="",
    )
    return gemini_key.strip()
