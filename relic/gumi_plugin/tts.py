"""Gemini TTS synthesis — converts text to voice for Telegram bubbles.

Output: OGG/Opus format (Telegram-compatible) via ffmpeg.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

VOICE_TRAIT_MAP = {
    ("female", "warm"): "Aoede",
    ("female", "expressive"): "Zephyr",
    ("female", "calm"): "Kore",
    ("male", "warm"): "Charon",
    ("male", "calm"): "Fenrir",
    "default": "Kore",
}

_ATTACHMENT_TO_TONE = {
    "secure attachment": "warm",
    "earned secure": "warm",
    "anxious attachment": "expressive",
    "disorganized attachment": "expressive",
    "avoidant attachment": "calm",
}


def select_voice_for_canon(background_profile: dict) -> str:
    """Select Gemini voice from domains.embodiment.gender_expression and attachment_style."""
    domains = background_profile.get("domains", {})
    embodiment = domains.get("embodiment", {})
    gender_expr = embodiment.get("gender_expression", "").lower()

    if gender_expr in ("feminine",):
        gender = "female"
    elif gender_expr in ("masculine",):
        gender = "male"
    else:
        gender = ""

    attachment = domains.get("relationship_stance", {}).get("attachment_style", "").lower()
    tone = _ATTACHMENT_TO_TONE.get(attachment, "calm")

    key = (gender, tone) if gender else "default"
    return VOICE_TRAIT_MAP.get(key, VOICE_TRAIT_MAP["default"])


def _load_voice_canon(relic_subject_home: Path) -> dict:
    """Load gumi_voice_canon.json."""
    path = relic_subject_home / "gumi_voice_canon.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def synthesize(
    text: str,
    voice_name: str,
    output_path: Path,
    api_key: str,
    model: str = GEMINI_TTS_MODEL,
) -> Path:
    """Synthesize text to speech via Gemini TTS, convert to OGG/Opus."""
    import requests

    url = f"{TTS_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }

    response = requests.post(url, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"TTS synthesis failed: {response.status_code} {response.text[:200]}")

    result = response.json()
    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    audio_content = None
    mime_type = "audio/pcm"
    for part in parts:
        if "inlineData" in part:
            audio_content = part["inlineData"].get("data")
            mime_type = part["inlineData"].get("mimeType", "audio/pcm")
            break

    if not audio_content:
        raise RuntimeError("No audio content in TTS response")

    import base64
    pcm_data = base64.standard_b64decode(audio_content)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Gemini TTS returns raw signed 16-bit PCM at 24kHz mono.
    # ffmpeg needs explicit format flags since there's no WAV header.
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp_pcm:
        tmp_pcm.write(pcm_data)
        tmp_pcm_path = tmp_pcm.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "s16le", "-ar", "24000", "-ac", "1",
                "-i", tmp_pcm_path,
                "-c:a", "libopus", "-b:a", "64k",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode() if e.stderr else str(e)}")
    finally:
        Path(tmp_pcm_path).unlink(missing_ok=True)

    return output_path


def strip_emoji(text: str) -> str:
    """Remove emoji characters from text before TTS synthesis."""
    import unicodedata
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Sm")
        and ord(ch) < 0x1F000  # exclude supplementary symbol blocks
        or ch in ("\n", "\t")
    ).strip()


def synthesize_checkin_audio(
    text: str,
    hermes_home: Path,
    relic_subject_home: Path,
    api_key: str,
) -> Path:
    """Synthesize checkin voice message, save to gumi-audio/."""
    voice_canon = _load_voice_canon(relic_subject_home)
    voice_id = voice_canon.get("voice_id", "Kore")

    tmp_dir = hermes_home / "tmp" / "gumi-audio"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = tmp_dir / f"voice_{timestamp}.ogg"

    return synthesize(strip_emoji(text), voice_id, output_path, api_key)
